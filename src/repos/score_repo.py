"""Repository for perception_scores."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class ScoreRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def get_perception_timeseries(
        self, project_id: str, start_date: str | None, end_date: str | None,
    ) -> list[aiosqlite.Row]:
        """SELECT perception scores for the perception chart."""
        clauses = ["project_id = ?", "term_id IS NULL", "provider_name IS NULL"]
        params: list[object] = [project_id]
        if start_date:
            clauses.append("period_start >= ?")
            params.append(f"{start_date}T00:00:00Z")
        if end_date:
            clauses.append("period_end <= ?")
            params.append(f"{end_date}T23:59:59.999999Z")

        where = " AND ".join(clauses)
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"SELECT * FROM perception_scores WHERE {where} ORDER BY period_start ASC",
                params,
            )
            return list(await cursor.fetchall())

    async def get_trajectory_timeseries(
        self, project_id: str, period: str, start_date: str | None, end_date: str | None,
    ) -> list[aiosqlite.Row]:
        """SELECT perception scores for the trajectory chart."""
        clauses = ["project_id = ?", "term_id IS NULL", "provider_name IS NULL", "period_type = ?"]
        params: list[object] = [project_id, period]
        if start_date:
            clauses.append("period_start >= ?")
            params.append(f"{start_date}T00:00:00Z")
        if end_date:
            clauses.append("period_end <= ?")
            params.append(f"{end_date}T23:59:59.999999Z")

        where = " AND ".join(clauses)
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"SELECT * FROM perception_scores WHERE {where} ORDER BY period_start ASC",
                params,
            )
            return list(await cursor.fetchall())

    async def get_previous_score(
        self,
        project_id: str,
        term_id: str | None,
        provider_name: str | None,
        cutoff: str,
    ) -> float | None:
        """Fetch the latest historical recommendation_share within a lookback window."""
        async with self._get_connection() as db:
            if term_id is not None and provider_name is not None:
                cursor = await db.execute(
                    "SELECT recommendation_share FROM perception_scores"
                    " WHERE project_id = ? AND term_id = ? AND provider_name = ? AND created_at > ?"
                    " ORDER BY created_at DESC LIMIT 1",
                    (project_id, term_id, provider_name, cutoff),
                )
            elif term_id is not None:
                cursor = await db.execute(
                    "SELECT recommendation_share FROM perception_scores"
                    " WHERE project_id = ? AND term_id = ? AND provider_name IS NULL AND created_at > ?"
                    " ORDER BY created_at DESC LIMIT 1",
                    (project_id, term_id, cutoff),
                )
            elif provider_name is not None:
                cursor = await db.execute(
                    "SELECT recommendation_share FROM perception_scores"
                    " WHERE project_id = ? AND term_id IS NULL AND provider_name = ? AND created_at > ?"
                    " ORDER BY created_at DESC LIMIT 1",
                    (project_id, provider_name, cutoff),
                )
            else:
                cursor = await db.execute(
                    "SELECT recommendation_share FROM perception_scores"
                    " WHERE project_id = ? AND term_id IS NULL AND provider_name IS NULL AND created_at > ?"
                    " ORDER BY created_at DESC LIMIT 1",
                    (project_id, cutoff),
                )
            row = await cursor.fetchone()
        if row is None:
            return None
        return float(row["recommendation_share"])

    async def get_run_responses_with_mentions(self, run_id: str) -> tuple[list[aiosqlite.Row], list[aiosqlite.Row]]:
        """Return (responses, mentions) for scoring calculation."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT r.id AS response_id, r.term_id, r.provider_name"
                " FROM responses r"
                " WHERE r.run_id = ? AND r.error_message IS NULL",
                (run_id,),
            )
            responses = list(await cursor.fetchall())

            if not responses:
                return [], []

            response_ids = [r["response_id"] for r in responses]
            placeholders = ",".join("?" for _ in response_ids)
            cursor = await db.execute(
                f"SELECT m.response_id, m.mention_type, m.target_name, m.list_position"
                f" FROM mentions m WHERE m.response_id IN ({placeholders})",
                response_ids,
            )
            mentions = list(await cursor.fetchall())
        return responses, mentions

    async def get_latest_breakdown_by_term(
        self, project_id: str,
    ) -> list[aiosqlite.Row]:
        """Return the most recent per-term aggregate scores."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT ps.term_id, ps.recommendation_share, ps.position_avg"
                " FROM perception_scores ps"
                " INNER JOIN ("
                "   SELECT term_id, MAX(created_at) AS max_created"
                "   FROM perception_scores"
                "   WHERE project_id = ? AND term_id IS NOT NULL AND provider_name IS NULL"
                "   GROUP BY term_id"
                " ) latest ON ps.term_id = latest.term_id AND ps.created_at = latest.max_created"
                " WHERE ps.project_id = ? AND ps.provider_name IS NULL",
                (project_id, project_id),
            )
            return list(await cursor.fetchall())

    async def get_latest_breakdown_by_provider(
        self, project_id: str,
    ) -> list[aiosqlite.Row]:
        """Return the most recent per-provider aggregate scores."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT ps.provider_name, ps.recommendation_share, ps.position_avg"
                " FROM perception_scores ps"
                " INNER JOIN ("
                "   SELECT provider_name, MAX(created_at) AS max_created"
                "   FROM perception_scores"
                "   WHERE project_id = ? AND term_id IS NULL AND provider_name IS NOT NULL"
                "   GROUP BY provider_name"
                " ) latest ON ps.provider_name = latest.provider_name AND ps.created_at = latest.max_created"
                " WHERE ps.project_id = ? AND ps.term_id IS NULL",
                (project_id, project_id),
            )
            return list(await cursor.fetchall())

    async def get_latest_run_counts(
        self, project_id: str,
    ) -> tuple[int, int, int]:
        """Return (total_responses, brand_mentions, ranked_responses) from the latest completed run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id FROM runs"
                " WHERE project_id = ? AND status = 'completed'"
                " ORDER BY completed_at DESC LIMIT 1",
                (project_id,),
            )
            run_row = await cursor.fetchone()
            if not run_row:
                return 0, 0, 0
            run_id = run_row["id"]

            cursor = await db.execute(
                "SELECT COUNT(*) AS total FROM responses"
                " WHERE run_id = ? AND error_message IS NULL",
                (run_id,),
            )
            total_row = await cursor.fetchone()
            total = total_row["total"] if total_row else 0

            cursor = await db.execute(
                "SELECT COUNT(DISTINCT resp.id) AS mentioned FROM responses resp"
                " INNER JOIN mentions m ON m.response_id = resp.id"
                " WHERE resp.run_id = ? AND resp.error_message IS NULL AND m.mention_type = 'brand'",
                (run_id,),
            )
            mention_row = await cursor.fetchone()
            mentions = mention_row["mentioned"] if mention_row else 0

            cursor = await db.execute(
                "SELECT COUNT(DISTINCT resp.id) AS ranked FROM responses resp"
                " INNER JOIN mentions m ON m.response_id = resp.id"
                " WHERE resp.run_id = ? AND resp.error_message IS NULL"
                " AND m.mention_type = 'brand' AND m.list_position IS NOT NULL",
                (run_id,),
            )
            ranked_row = await cursor.fetchone()
            ranked = ranked_row["ranked"] if ranked_row else 0

        return total, mentions, ranked

    async def store_scores(
        self,
        project_id: str,
        scores: list[tuple[str | None, str | None, float, float | None, float | None, float, str, str, str, str]],
        period_type: str,
        now: str,
    ) -> list[str]:
        """Batch INSERT perception scores. Returns list of score IDs."""
        if not scores:
            return []

        ids: list[str] = []
        async with self._get_connection() as db:
            for score in scores:
                score_id = uuid.uuid4().hex
                await db.execute(
                    "INSERT INTO perception_scores"
                    " (id, project_id, term_id, provider_name, recommendation_share,"
                    "  position_avg, competitor_delta, overall_score, trend_direction,"
                    "  period_type, period_start, period_end, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        score_id,
                        project_id,
                        score[0],  # term_id
                        score[1],  # provider_name
                        score[2],  # recommendation_share
                        score[3],  # position_avg
                        score[4],  # competitor_delta
                        score[5],  # overall_score
                        score[6],  # trend_direction
                        period_type,
                        now,
                        now,
                        now,
                    ),
                )
                ids.append(score_id)
            await db.commit()
        return ids
