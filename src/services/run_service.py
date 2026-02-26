"""Service layer for runs and responses."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.schemas import (
    MentionItem,
    PaginatedResponse,
    PerceptionBreakdownByProvider,
    PerceptionBreakdownByTerm,
    PerceptionBreakdownResponse,
    PerceptionDataPoint,
    PerceptionResponse,
    ResponseItem,
    RunDetailResponse,
    RunResponse,
    TrajectoryDataPoint,
    TrajectoryResponse,
)

if TYPE_CHECKING:
    import aiosqlite

    from src.repos.response_repo import ResponseRepo
    from src.repos.run_repo import RunRepo
    from src.repos.score_repo import ScoreRepo
    from src.repos.term_repo import TermRepo


class RunService:
    def __init__(
        self, run_repo: RunRepo, response_repo: ResponseRepo, score_repo: ScoreRepo,
        term_repo: TermRepo | None = None,
    ) -> None:
        self._run_repo = run_repo
        self._response_repo = response_repo
        self._score_repo = score_repo
        self._term_repo = term_repo

    async def list_runs(
        self, project_id: str, limit: int, offset: int, status: str | None,
    ) -> PaginatedResponse[RunResponse]:
        """Paginated runs for a project."""
        total, rows = await self._run_repo.list_runs(project_id, limit, offset, status)
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
        return PaginatedResponse[RunResponse](items=items, total=total, limit=limit, offset=offset)

    async def get_run_detail(self, run_id: str) -> RunDetailResponse | None:
        """Run detail with perception score and competitors detected."""
        run = await self._run_repo.get_run(run_id)
        if not run:
            return None

        score_row = await self._run_repo.get_aggregate_perception_score(run["project_id"])
        perception_score: float | None = None
        recommendation_share: float | None = None
        if score_row:
            perception_score = score_row["overall_score"]
            recommendation_share = score_row["recommendation_share"]

        competitors_detected = await self._run_repo.get_competitors_detected(run_id)

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

    async def get_run_status(self, run_id: str) -> aiosqlite.Row | None:
        """Return status/progress columns for SSE."""
        return await self._run_repo.get_run_status(run_id)

    async def list_responses(
        self, run_id: str, project_id: str, limit: int, offset: int,
    ) -> PaginatedResponse[ResponseItem]:
        """Paginated responses with batch-loaded mentions (fixes N+1)."""
        total, resp_rows = await self._response_repo.list_responses_for_run(run_id, limit, offset)

        # Build term_id -> name lookup
        term_names: dict[str, str] = {}
        if self._term_repo is not None:
            term_rows = await self._term_repo.list_active_term_ids_and_names(project_id)
            term_names = {row["id"]: row["name"] for row in term_rows}

        response_ids = [r["id"] for r in resp_rows]
        mention_rows = await self._response_repo.get_mentions_for_responses(response_ids)

        # Build lookup: response_id -> list[mention_row]
        mention_map: dict[str, list[Any]] = defaultdict(list)
        for m in mention_rows:
            mention_map[m["response_id"]].append(m)

        items: list[ResponseItem] = []
        for resp_row in resp_rows:
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
                for m in mention_map.get(resp_row["id"], [])
            ]
            items.append(
                ResponseItem(
                    id=resp_row["id"],
                    run_id=resp_row["run_id"],
                    term_id=resp_row["term_id"],
                    term_name=term_names.get(resp_row["term_id"], resp_row["term_id"]),
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

        return PaginatedResponse[ResponseItem](items=items, total=total, limit=limit, offset=offset)

    async def get_perception(
        self, project_id: str, start_date: str | None, end_date: str | None,
    ) -> PerceptionResponse:
        """Perception timeseries data."""
        rows = await self._score_repo.get_perception_timeseries(project_id, start_date, end_date)
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
        return PerceptionResponse(project_id=project_id, data=data)

    async def get_trajectory(
        self, project_id: str, start_date: str | None, end_date: str | None, period: str,
    ) -> TrajectoryResponse:
        """Trajectory timeseries data."""
        rows = await self._score_repo.get_trajectory_timeseries(project_id, period, start_date, end_date)
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
        return TrajectoryResponse(project_id=project_id, data=data)

    async def get_perception_breakdown(
        self, project_id: str, term_names: dict[str, str],
    ) -> PerceptionBreakdownResponse:
        """Per-term and per-provider breakdown from the latest scoring period."""
        total_responses, brand_mentions, ranked_responses = await self._score_repo.get_latest_run_counts(project_id)
        by_term_rows = await self._score_repo.get_latest_breakdown_by_term(project_id)
        by_provider_rows = await self._score_repo.get_latest_breakdown_by_provider(project_id)

        by_term = [
            PerceptionBreakdownByTerm(
                term_id=row["term_id"],
                term_name=term_names.get(row["term_id"], row["term_id"]),
                recommendation_share=row["recommendation_share"],
                position_avg=row["position_avg"],
            )
            for row in by_term_rows
        ]
        by_provider = [
            PerceptionBreakdownByProvider(
                provider_name=row["provider_name"],
                recommendation_share=row["recommendation_share"],
                position_avg=row["position_avg"],
            )
            for row in by_provider_rows
        ]

        return PerceptionBreakdownResponse(
            project_id=project_id,
            total_responses=total_responses,
            brand_mentions=brand_mentions,
            ranked_responses=ranked_responses,
            by_term=by_term,
            by_provider=by_provider,
        )
