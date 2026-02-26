"""Scheduling loop for GeoStorm monitoring runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import logfire

from src.database import get_db_connection
from src.llm.base import LLMError, PromptRequest, PromptResponse, ProviderType, with_web_search
from src.llm.client import send_prompt
from src.llm.prompt_service import generate_prompt, get_system_prompt
from src.progress import RunPhase, RunProgressEvent, progress_bus

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


async def scheduling_loop() -> None:
    """Main scheduling loop — called every 60s by APScheduler."""
    with logfire.span('scheduling loop'):
        logger.info("Scheduling loop running")
        now = datetime.now(tz=UTC)

        try:
            async with get_db_connection() as db:
                cursor = await db.execute(
                    """
                    SELECT ps.id, ps.project_id, ps.hour_of_day, ps.days_of_week_json, ps.last_run_at
                    FROM project_schedules ps
                    JOIN projects p ON p.id = ps.project_id
                    WHERE ps.is_active = 1 AND p.is_demo = 0 AND p.deleted_at IS NULL
                    """,
                )
                schedules = await cursor.fetchall()

            for schedule in schedules:
                if should_run_schedule(schedule, now):
                    project_id: str = schedule["project_id"]
                    schedule_id: str = schedule["id"]
                    logger.info("Schedule %s is due for project %s", schedule_id, project_id)
                    try:
                        run_id = await execute_monitoring_run(
                            project_id=project_id,
                            schedule_id=schedule_id,
                            trigger_type="scheduled",
                        )
                        logger.info("Monitoring run %s completed for project %s", run_id, project_id)
                    except Exception:
                        logger.exception("Failed to execute monitoring run for project %s", project_id)

        except Exception:
            logger.exception("Error in scheduling loop")


def should_run_schedule(schedule: object, current_time: datetime) -> bool:
    """Determine if a schedule is due to run."""
    hour_of_day: int = schedule["hour_of_day"]  # type: ignore[index]
    days_json: str = schedule["days_of_week_json"]  # type: ignore[index]
    last_run_at_raw: str | None = schedule["last_run_at"]  # type: ignore[index]

    days_of_week: list[int] = json.loads(days_json)
    if current_time.weekday() not in days_of_week:
        return False

    if current_time.hour != hour_of_day:
        return False

    if last_run_at_raw:
        last_run_at = datetime.fromisoformat(last_run_at_raw)
        last_utc = last_run_at.replace(tzinfo=UTC)
        if (
            last_utc.year == current_time.year
            and last_utc.month == current_time.month
            and last_utc.day == current_time.day
            and last_utc.hour == current_time.hour
        ):
            return False

    return True


async def execute_monitoring_run(
    project_id: str,
    schedule_id: str | None = None,
    trigger_type: str = "manual",
) -> str:
    """Execute a monitoring run for a project.

    Creates a Run record, iterates over all (term x provider) combinations,
    calls the LLM, and stores responses.
    """
    run_id = uuid.uuid4().hex
    with logfire.span('monitoring run', run_id=run_id, project_id=project_id, trigger_type=trigger_type):
        now_iso = datetime.now(tz=UTC).isoformat()
        terms, providers = await _load_run_inputs(project_id)

        if not terms or not providers:
            logger.warning("No active terms or providers for project %s, skipping run", project_id)
            return run_id

        total_queries = len(terms) * len(providers)
        await _create_run_record(run_id, project_id, trigger_type, total_queries, now_iso)

        progress_bus.publish(RunProgressEvent(
            run_id=run_id, phase=RunPhase.preparing,
            completed=0, failed=0, total=total_queries,
        ))

        completed, failed = await _execute_queries(run_id, project_id, terms, providers)
        await _finalize_run(run_id, project_id, schedule_id, completed, failed)

        return run_id


async def _load_run_inputs(project_id: str) -> tuple[Sequence[Any], Sequence[Any]]:
    """Load active terms and enabled providers for a project."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id, name FROM project_terms WHERE project_id = ? AND is_active = 1",
            (project_id,),
        )
        terms = list(await cursor.fetchall())

        cursor = await db.execute(
            "SELECT provider_name, model_name FROM llm_providers WHERE project_id = ? AND is_enabled = 1",
            (project_id,),
        )
        providers = list(await cursor.fetchall())

    return terms, providers


async def _create_run_record(
    run_id: str, project_id: str, trigger_type: str, total_queries: int, now_iso: str,
) -> None:
    """Insert a new run record into the database."""
    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, project_id, "running", trigger_type, total_queries, now_iso, now_iso),
        )
        await db.commit()


async def _execute_queries(
    run_id: str, project_id: str, terms: Sequence[Any], providers: Sequence[Any],
) -> tuple[int, int]:
    """Execute all term x provider queries in parallel (up to 3 concurrent) and return (completed, failed) counts."""
    total_queries = len(terms) * len(providers)
    system_prompt = get_system_prompt()
    semaphore = asyncio.Semaphore(3)
    completed_queries = 0
    failed_queries = 0
    lock = asyncio.Lock()

    async def _run_one(term: Any, provider_row: Any) -> None:
        nonlocal completed_queries, failed_queries
        term_id: str = term["id"]
        term_name: str = term["name"]
        prompt_text = generate_prompt(term_name)
        provider_name: str = provider_row["provider_name"]
        model_name: str = provider_row["model_name"]

        async with semaphore:
            progress_bus.publish(RunProgressEvent(
                run_id=run_id, phase=RunPhase.querying,
                completed=completed_queries, failed=failed_queries, total=total_queries,
                current_term=term_name, current_provider=provider_name,
            ))

            success = await _execute_single_query(
                run_id, project_id, term_id, provider_name, model_name, prompt_text, system_prompt,
            )

            async with lock:
                if success:
                    completed_queries += 1
                else:
                    failed_queries += 1

                await _update_run_progress(run_id, completed_queries, failed_queries)

                progress_bus.publish(RunProgressEvent(
                    run_id=run_id, phase=RunPhase.querying,
                    completed=completed_queries, failed=failed_queries, total=total_queries,
                    current_term=term_name, current_provider=provider_name,
                ))

    await asyncio.gather(*[
        _run_one(term, provider_row)
        for term in terms
        for provider_row in providers
    ])

    return completed_queries, failed_queries


async def _update_run_progress(run_id: str, completed: int, failed: int) -> None:
    """Incrementally update run progress in the database after each query."""
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE runs SET completed_queries = ?, failed_queries = ? WHERE id = ?",
            (completed, failed, run_id),
        )
        await db.commit()


async def _execute_single_query(  # noqa: PLR0913
    run_id: str,
    project_id: str,
    term_id: str,
    provider_name: str,
    model_name: str,
    prompt_text: str,
    system_prompt: str,
) -> bool:
    """Execute a single LLM query. Returns True on success, False on failure."""
    with logfire.span('LLM query', provider=provider_name, model=model_name):
        try:
            provider_type = ProviderType(provider_name)
        except ValueError:
            logger.warning("Unknown provider type: %s", provider_name)
            await _store_error_response(run_id, project_id, term_id, provider_name, model_name,
                                        f"Unknown provider type: {provider_name}")
            return False

        try:
            online_model = with_web_search(model_name)
            request = PromptRequest(prompt=prompt_text, model_id=online_model, system_prompt=system_prompt)
            response = await send_prompt(request, provider_type)
            await _store_response(run_id, project_id, term_id, provider_name, model_name, response)
        except LLMError as e:
            logger.warning("LLM error for %s/%s: %s", provider_name, model_name, e)
            await _store_error_response(run_id, project_id, term_id, provider_name, model_name, str(e))
            return False
        except Exception:
            logger.exception("Unexpected error for %s/%s", provider_name, model_name)
            await _store_error_response(run_id, project_id, term_id, provider_name, model_name, "Unexpected error")
            return False

        return True


async def _finalize_run(run_id: str, project_id: str, schedule_id: str | None, completed: int, failed: int) -> None:
    """Update the run record with final status and update schedule timestamp."""
    final_status = "completed" if completed > 0 else "failed"
    completed_at = datetime.now(tz=UTC).isoformat()

    async with get_db_connection() as db:
        await db.execute(
            """
            UPDATE runs SET status = ?, completed_queries = ?, failed_queries = ?, completed_at = ?
            WHERE id = ?
            """,
            (final_status, completed, failed, completed_at, run_id),
        )

        if schedule_id:
            await db.execute(
                "UPDATE project_schedules SET last_run_at = ? WHERE id = ?",
                (completed_at, schedule_id),
            )

        await db.commit()

    logger.info("Run %s finished: status=%s, completed=%d, failed=%d", run_id, final_status, completed, failed)

    total = completed + failed

    if final_status == "completed":
        progress_bus.publish(RunProgressEvent(
            run_id=run_id, phase=RunPhase.analyzing,
            completed=completed, failed=failed, total=total,
            status="running",
        ))
        try:
            from src.services.analysis import analyze_run  # noqa: PLC0415
            await analyze_run(run_id, project_id)
        except Exception:
            logger.exception("Analysis pipeline failed for run %s", run_id)

    final_phase = RunPhase.complete if final_status == "completed" else RunPhase.failed
    progress_bus.publish(RunProgressEvent(
        run_id=run_id, phase=final_phase,
        completed=completed, failed=failed, total=total,
        status=final_status,
    ))


async def _store_response(  # noqa: PLR0913
    run_id: str,
    project_id: str,
    term_id: str,
    provider_name: str,
    model_name: str,
    response: PromptResponse,
) -> None:
    """Store a successful LLM response in the database."""
    response_id = uuid.uuid4().hex
    now_iso = datetime.now(tz=UTC).isoformat()

    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO responses
                (id, run_id, project_id, term_id, provider_name, model_name,
                 response_text, latency_ms, token_count_prompt, token_count_completion,
                 cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response_id, run_id, project_id, term_id, provider_name, model_name,
                response.text, response.latency_ms, response.prompt_tokens, response.completion_tokens,
                response.cost_usd, now_iso,
            ),
        )
        await db.commit()


async def _store_error_response(  # noqa: PLR0913
    run_id: str,
    project_id: str,
    term_id: str,
    provider_name: str,
    model_name: str,
    error_message: str,
) -> None:
    """Store a failed LLM response (dead-letter) in the database."""
    response_id = uuid.uuid4().hex
    now_iso = datetime.now(tz=UTC).isoformat()

    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO responses
                (id, run_id, project_id, term_id, provider_name, model_name,
                 response_text, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (response_id, run_id, project_id, term_id, provider_name, model_name, "", error_message, now_iso),
        )
        await db.commit()
