"""Scheduling loop for GeoStorm monitoring runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import logfire

from src.analytics import capture_run_completed
from src.container import alert_repo, provider_repo, response_repo, run_repo, schedule_repo, term_repo
from src.llm.base import LLMError, PromptRequest, ProviderType, with_web_search
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
            schedules = await schedule_repo.get_active_schedules()

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
    """Execute a monitoring run for a project."""
    run_id = uuid.uuid4().hex
    with logfire.span('monitoring run', run_id=run_id, project_id=project_id, trigger_type=trigger_type):
        now_iso = datetime.now(tz=UTC).isoformat()
        terms = await term_repo.list_active_term_ids_and_names(project_id)
        providers = await provider_repo.list_enabled_providers(project_id)

        if not terms or not providers:
            logger.warning("No active terms or providers for project %s, skipping run", project_id)
            missing = []
            if not terms:
                missing.append("monitoring terms")
            if not providers:
                missing.append("LLM providers")
            missing_str = " and ".join(missing)
            await alert_repo.store_alerts([(
                project_id,
                "configuration_error",
                "critical",
                f"Monitoring run skipped — no {missing_str} configured",
                f"A {trigger_type} monitoring run was skipped because this project has no {missing_str}. "
                "To fix this, open your project's detail page, scroll to the Monitoring Terms section, "
                "and add at least one term describing what users would ask an AI when looking for a tool "
                "like yours (e.g. \"best Python web framework\" or \"top API testing tools\"). "
                "Runs will continue to be skipped until this is resolved.",
                "{}",
            )])
            return run_id

        total_queries = len(terms) * len(providers)
        await run_repo.create_run(run_id, project_id, trigger_type, total_queries, now_iso)

        progress_bus.publish(RunProgressEvent(
            run_id=run_id, phase=RunPhase.preparing,
            completed=0, failed=0, total=total_queries,
        ))

        completed, failed = await _execute_queries(run_id, project_id, terms, providers)
        await _finalize_run(run_id, project_id, schedule_id, completed, failed)

        return run_id


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

    async def _run_one(
        term: Any, provider_row: Any,  # noqa: ANN401
    ) -> None:
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

                await run_repo.update_run_progress(run_id, completed_queries, failed_queries)

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
            await response_repo.store_error_response(
                run_id, project_id, term_id, provider_name, model_name,
                f"Unknown provider type: {provider_name}",
            )
            return False

        try:
            online_model = with_web_search(model_name)
            request = PromptRequest(prompt=prompt_text, model_id=online_model, system_prompt=system_prompt)
            response = await send_prompt(request, provider_type)
            await response_repo.store_response(
                run_id, project_id, term_id, provider_name, model_name,
                response.text, response.latency_ms, response.prompt_tokens,
                response.completion_tokens, response.cost_usd,
            )
        except LLMError as e:
            logger.warning("LLM error for %s/%s: %s", provider_name, model_name, e)
            await response_repo.store_error_response(
                run_id, project_id, term_id, provider_name, model_name, str(e),
            )
            return False
        except Exception:
            logger.exception("Unexpected error for %s/%s", provider_name, model_name)
            await response_repo.store_error_response(
                run_id, project_id, term_id, provider_name, model_name, "Unexpected error",
            )
            return False

        return True


async def _finalize_run(run_id: str, project_id: str, schedule_id: str | None, completed: int, failed: int) -> None:
    """Update the run record with final status and update schedule timestamp."""
    final_status = "completed" if completed > 0 else "failed"
    completed_at = datetime.now(tz=UTC).isoformat()

    await run_repo.finalize_run(run_id, final_status, completed, failed, completed_at)

    if schedule_id:
        await schedule_repo.update_last_run_at(schedule_id, completed_at)

    logger.info("Run %s finished: status=%s, completed=%d, failed=%d", run_id, final_status, completed, failed)
    capture_run_completed()

    total = completed + failed

    if final_status == "completed":
        progress_bus.publish(RunProgressEvent(
            run_id=run_id, phase=RunPhase.analyzing,
            completed=completed, failed=failed, total=total,
            status="running",
        ))
        try:
            from src.container import analysis_service  # noqa: PLC0415
            await analysis_service.analyze_run(run_id, project_id)
        except Exception:
            logger.exception("Analysis pipeline failed for run %s", run_id)

    final_phase = RunPhase.complete if final_status == "completed" else RunPhase.failed
    progress_bus.publish(RunProgressEvent(
        run_id=run_id, phase=final_phase,
        completed=completed, failed=failed, total=total,
        status=final_status,
    ))
