"""Run, response, and perception endpoints for GeoStorm API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from src.database import get_db_connection
from src.routes.deps import get_project_or_404
from src.schemas import (
    MentionItem,
    PaginatedResponse,
    PerceptionDataPoint,
    PerceptionResponse,
    ResponseItem,
    RunDetailResponse,
    RunResponse,
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


# ---------------------------------------------------------------------------
# 3) GET /api/runs/{run_id}/responses
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
        params.append(start_date)
    if end_date:
        clauses.append("period_end <= ?")
        params.append(end_date)

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
