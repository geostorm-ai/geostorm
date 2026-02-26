"""Repository for change detection read queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import MentionType

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class ChangeDetectionRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def get_baseline_averages(self, project_id: str, cutoff: str) -> aiosqlite.Row | None:
        """AVG recommendation_share, position_avg in baseline window."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT AVG(recommendation_share) AS avg_share, AVG(position_avg) AS avg_pos"
                " FROM perception_scores"
                " WHERE project_id = ? AND created_at > ?",
                (project_id, cutoff),
            )
            return await cursor.fetchone()

    async def get_baseline_provider_shares(self, project_id: str, cutoff: str) -> list[aiosqlite.Row]:
        """Per-provider AVG recommendation_share in baseline window."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT provider_name, AVG(recommendation_share) AS avg_share"
                " FROM perception_scores"
                " WHERE project_id = ? AND provider_name IS NOT NULL AND created_at > ?"
                " GROUP BY provider_name",
                (project_id, cutoff),
            )
            return list(await cursor.fetchall())

    async def get_baseline_competitors(self, project_id: str, cutoff: str) -> set[str]:
        """DISTINCT competitor names in baseline window."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT DISTINCT m.target_name"
                " FROM mentions m"
                " JOIN responses r ON m.response_id = r.id"
                " WHERE r.project_id = ? AND m.mention_type = ? AND m.detected_at > ?",
                (project_id, MentionType.COMPETITOR.value, cutoff),
            )
            return {row["target_name"] for row in await cursor.fetchall()}

    async def get_run_competitor_names(self, run_id: str, project_id: str) -> list[str]:
        """DISTINCT competitors in a run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT DISTINCT m.target_name"
                " FROM mentions m"
                " JOIN responses r ON m.response_id = r.id"
                " WHERE r.run_id = ? AND r.project_id = ? AND m.mention_type = ?",
                (run_id, project_id, MentionType.COMPETITOR.value),
            )
            return [row["target_name"] for row in await cursor.fetchall()]

    async def count_run_responses(self, run_id: str, project_id: str) -> int:
        """COUNT non-error responses in a run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS total"
                " FROM responses WHERE run_id = ? AND project_id = ? AND error_message IS NULL",
                (run_id, project_id),
            )
            row = await cursor.fetchone()
            return row["total"] if row else 0

    async def count_brand_mentions_in_run(self, run_id: str, project_id: str) -> int:
        """COUNT distinct responses with brand mention in a run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT r.id) AS brand_count"
                " FROM responses r"
                " JOIN mentions m ON m.response_id = r.id"
                " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
                "   AND m.mention_type = ?",
                (run_id, project_id, MentionType.BRAND.value),
            )
            row = await cursor.fetchone()
            return row["brand_count"] if row else 0

    async def get_avg_brand_position(self, run_id: str, project_id: str) -> float | None:
        """AVG list_position for brand mentions in a run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT AVG(m.list_position) AS avg_pos"
                " FROM mentions m"
                " JOIN responses r ON m.response_id = r.id"
                " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
                "   AND m.mention_type = ? AND m.list_position IS NOT NULL",
                (run_id, project_id, MentionType.BRAND.value),
            )
            row = await cursor.fetchone()
            if row and row["avg_pos"] is not None:
                return float(row["avg_pos"])
            return None

    async def get_per_provider_brand_shares(self, run_id: str, project_id: str) -> list[aiosqlite.Row]:
        """Per-provider brand share for divergence detection."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT r.provider_name,"
                "   COUNT(DISTINCT r.id) AS total,"
                "   COUNT(DISTINCT CASE WHEN m.mention_type = ? THEN r.id END) AS brand_count"
                " FROM responses r"
                " LEFT JOIN mentions m ON m.response_id = r.id AND m.mention_type = ?"
                " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
                " GROUP BY r.provider_name",
                (MentionType.BRAND.value, MentionType.BRAND.value, run_id, project_id),
            )
            return list(await cursor.fetchall())
