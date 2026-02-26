"""Run, response, perception, and analytics endpoints for GeoStorm API."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.database import get_db_connection
from src.progress import RunPhase, RunProgressEvent, progress_bus
from src.routes.deps import get_project_or_404
from src.schemas import (
    MentionItem,
    PaginatedResponse,
    PerceptionDataPoint,
    PerceptionResponse,
    ResponseItem,
    RunDetailResponse,
    RunResponse,
    TrajectoryDataPoint,
    TrajectoryResponse,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# 1) GET /api/projects/{project_id}/runs
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/runs")
async def list_runs(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> PaginatedResponse[RunResponse]:
    """Paginated list of runs for a project."""
    await get_project_or_404(project_id)

    clauses = ["project_id = ?"]
    params: list[object] = [project_id]
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " AND ".join(clauses)

    async with get_db_connection() as db:
        # Count
        count_query = f"SELECT COUNT(*) FROM runs WHERE {where}"
        cursor = await db.execute(count_query, params)
        count_row = await cursor.fetchone()
        total: int = count_row[0] if count_row else 0

        # Data
        data_query = f"SELECT * FROM runs WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        cursor = await db.execute(data_query, [*params, limit, offset])
        rows = await cursor.fetchall()

    items = [
        RunResponse(
            id=r["id"],
            project_id=r["project_id"],
            status=r["status"],
            trigger_type=r["trigger_type"],
            triggered_by=r["triggered_by"],
            total_queries=r["total_queries"],
            completed_queries=r["completed_queries"],
            failed_queries=r["failed_queries"],
            started_at=datetime.fromisoformat(r["started_at"]) if r["started_at"] else None,
            completed_at=datetime.fromisoformat(r["completed_at"]) if r["completed_at"] else None,
            created_at=datetime.fromisoformat(r["created_at"]),
        )
        for r in rows
    ]

    return PaginatedResponse[RunResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# 2) GET /api/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunDetailResponse:
    """Run detail with aggregate perception score and competitors detected."""
    async with get_db_connection() as db:
        # Fetch the run
        cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Aggregate perception score (term_id IS NULL AND provider_name IS NULL = aggregate row)
        cursor = await db.execute(
            "SELECT overall_score, recommendation_share FROM perception_scores"
            " WHERE project_id = ? AND term_id IS NULL AND provider_name IS NULL"
            " ORDER BY created_at DESC LIMIT 1",
            (run["project_id"],),
        )
        score_row = await cursor.fetchone()

        perception_score: float | None = None
        recommendation_share: float | None = None
        if score_row:
            perception_score = score_row["overall_score"]
            recommendation_share = score_row["recommendation_share"]

        # Competitors detected
        cursor = await db.execute(
            "SELECT DISTINCT m.target_name FROM mentions m"
            " JOIN responses r ON r.id = m.response_id"
            " WHERE r.run_id = ? AND m.mention_type = 'competitor'",
            (run_id,),
        )
        competitor_rows = await cursor.fetchall()
        competitors_detected = [c["target_name"] for c in competitor_rows]

    return RunDetailResponse(
        id=run["id"],
        project_id=run["project_id"],
        status=run["status"],
        trigger_type=run["trigger_type"],
        triggered_by=run["triggered_by"],
        total_queries=run["total_queries"],
        completed_queries=run["completed_queries"],
        failed_queries=run["failed_queries"],
        started_at=datetime.fromisoformat(run["started_at"]) if run["started_at"] else None,
        completed_at=datetime.fromisoformat(run["completed_at"]) if run["completed_at"] else None,
        created_at=datetime.fromisoformat(run["created_at"]),
        perception_score=perception_score,
        recommendation_share=recommendation_share,
        competitors_detected=competitors_detected,
    )


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 3) GET /api/runs/{run_id}/progress  (SSE)
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/progress")
async def stream_run_progress(run_id: str) -> StreamingResponse:
    """Server-Sent Events stream for real-time run progress."""
    # Verify run exists
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT status, completed_queries, failed_queries, total_queries FROM runs WHERE id = ?",
            (run_id,),
        )
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        status = run["status"]
        # If already done, send a single final event and close
        if status in ("completed", "failed", "cancelled"):
            phase = RunPhase.complete if status == "completed" else RunPhase.failed
            event = RunProgressEvent(
                run_id=run_id, phase=phase,
                completed=run["completed_queries"], failed=run["failed_queries"],
                total=run["total_queries"], status=status,
            )
            yield f"data: {json.dumps(event.to_dict())}\n\n"
            return

        # Send an initial snapshot so the client renders immediately
        initial = RunProgressEvent(
            run_id=run_id,
            phase=RunPhase.preparing if status == "pending" else RunPhase.querying,
            completed=run["completed_queries"],
            failed=run["failed_queries"],
            total=run["total_queries"],
            status=status,
        )
        yield f"data: {json.dumps(initial.to_dict())}\n\n"

        queue = progress_bus.subscribe(run_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event.to_dict())}\n\n"
                    # Close stream when run finishes
                    if event.phase in (RunPhase.complete, RunPhase.failed):
                        return
                except TimeoutError:
                    # Keepalive comment to prevent proxy/browser timeout
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return
        finally:
            progress_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 4) GET /api/runs/{run_id}/responses
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/responses")
async def list_responses(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[ResponseItem]:
    """Paginated responses with nested mentions for a run."""
    async with get_db_connection() as db:
        # Verify run exists
        cursor = await db.execute("SELECT id FROM runs WHERE id = ?", (run_id,))
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM responses WHERE run_id = ?", (run_id,),
        )
        count_row = await cursor.fetchone()
        total: int = count_row[0] if count_row else 0

        # Fetch paginated responses
        cursor = await db.execute(
            "SELECT * FROM responses WHERE run_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (run_id, limit, offset),
        )
        resp_rows = await cursor.fetchall()

        # For each response, fetch its mentions
        items: list[ResponseItem] = []
        for resp_row in resp_rows:
            mention_cursor = await db.execute(
                "SELECT * FROM mentions WHERE response_id = ?", (resp_row["id"],),
            )
            mention_rows = await mention_cursor.fetchall()
            mentions = [
                MentionItem(
                    id=m["id"],
                    mention_type=m["mention_type"],
                    target_name=m["target_name"],
                    position_chars=m["position_chars"],
                    position_words=m["position_words"],
                    list_position=m["list_position"],
                    context_before=m["context_before"] or "",
                    context_after=m["context_after"] or "",
                )
                for m in mention_rows
            ]
            items.append(
                ResponseItem(
                    id=resp_row["id"],
                    run_id=resp_row["run_id"],
                    term_id=resp_row["term_id"],
                    provider_name=resp_row["provider_name"],
                    model_name=resp_row["model_name"],
                    response_text=resp_row["response_text"],
                    latency_ms=resp_row["latency_ms"],
                    cost_usd=resp_row["cost_usd"],
                    error_message=resp_row["error_message"],
                    created_at=datetime.fromisoformat(resp_row["created_at"]),
                    mentions=mentions,
                ),
            )

    return PaginatedResponse[ResponseItem](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# 4) GET /api/projects/{project_id}/perception
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/perception")
async def get_perception(
    project_id: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> PerceptionResponse:
    """Time-series perception data for a project."""
    await get_project_or_404(project_id)

    clauses = ["project_id = ?", "term_id IS NULL", "provider_name IS NULL"]
    params: list[object] = [project_id]
    if start_date:
        clauses.append("period_start >= ?")
        params.append(f"{start_date}T00:00:00Z")
    if end_date:
        clauses.append("period_end <= ?")
        params.append(f"{end_date}T23:59:59.999999Z")

    where = " AND ".join(clauses)

    async with get_db_connection() as db:
        cursor = await db.execute(
            f"SELECT * FROM perception_scores WHERE {where} ORDER BY period_start ASC",
            params,
        )
        rows = await cursor.fetchall()

    data = [
        PerceptionDataPoint(
            date=row["period_start"][:10],
            overall_score=row["overall_score"],
            recommendation_share=row["recommendation_share"],
            position_avg=row["position_avg"],
            competitor_delta=row["competitor_delta"],
            trend_direction=row["trend_direction"],
        )
        for row in rows
    ]

    return PerceptionResponse(
        project_id=project_id,
        data=data,
    )


# ---------------------------------------------------------------------------
# 5) GET /api/projects/{project_id}/trajectory
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/trajectory")
async def get_trajectory(
    project_id: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    period: Literal["daily", "weekly", "monthly"] = Query(default="weekly"),
) -> TrajectoryResponse:
    """Historical trajectory data showing week-over-week or day-over-day changes."""
    await get_project_or_404(project_id)

    clauses = ["project_id = ?", "term_id IS NULL", "provider_name IS NULL", "period_type = ?"]
    params: list[object] = [project_id, period]
    if start_date:
        clauses.append("period_start >= ?")
        params.append(f"{start_date}T00:00:00Z")
    if end_date:
        clauses.append("period_end <= ?")
        params.append(f"{end_date}T23:59:59.999999Z")

    where = " AND ".join(clauses)

    async with get_db_connection() as db:
        cursor = await db.execute(
            f"SELECT * FROM perception_scores WHERE {where} ORDER BY period_start ASC",
            params,
        )
        rows = await cursor.fetchall()

    data = [
        TrajectoryDataPoint(
            date=row["period_start"][:10],
            recommendation_share=row["recommendation_share"],
            position_avg=row["position_avg"],
            competitor_delta=row["competitor_delta"],
            trend_direction=row["trend_direction"],
        )
        for row in rows
    ]

    return TrajectoryResponse(
        project_id=project_id,
        data=data,
    )
