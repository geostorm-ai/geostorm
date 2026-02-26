"""Repository for runs and cascade cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class RunRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def list_runs(
        self,
        project_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
    ) -> tuple[int, list[aiosqlite.Row]]:
        """COUNT + SELECT runs with pagination. Returns (total, rows)."""
        clauses = ["project_id = ?"]
        params: list[object] = [project_id]
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses)

        async with self._get_connection() as db:
            cursor = await db.execute(f"SELECT COUNT(*) FROM runs WHERE {where}", params)
            count_row = await cursor.fetchone()
            total: int = count_row[0] if count_row else 0

            cursor = await db.execute(
                f"SELECT * FROM runs WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
            rows = list(await cursor.fetchall())
        return total, rows

    async def get_run(self, run_id: str) -> aiosqlite.Row | None:
        """SELECT a run by id."""
        async with self._get_connection() as db:
            cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            return await cursor.fetchone()

    async def get_run_status(self, run_id: str) -> aiosqlite.Row | None:
        """SELECT status/progress columns only."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT status, completed_queries, failed_queries, total_queries FROM runs WHERE id = ?",
                (run_id,),
            )
            return await cursor.fetchone()

    async def create_run(
        self, run_id: str, project_id: str, trigger_type: str, total_queries: int, now_iso: str,
    ) -> None:
        """INSERT a new run record."""
        async with self._get_connection() as db:
            await db.execute(
                """
                INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, project_id, "running", trigger_type, total_queries, now_iso, now_iso),
            )
            await db.commit()

    async def update_run_progress(self, run_id: str, completed: int, failed: int) -> None:
        """UPDATE progress counters."""
        async with self._get_connection() as db:
            await db.execute(
                "UPDATE runs SET completed_queries = ?, failed_queries = ? WHERE id = ?",
                (completed, failed, run_id),
            )
            await db.commit()

    async def finalize_run(
        self, run_id: str, status: str, completed: int, failed: int, completed_at: str,
    ) -> None:
        """UPDATE final status on a run."""
        async with self._get_connection() as db:
            await db.execute(
                """
                UPDATE runs SET status = ?, completed_queries = ?, failed_queries = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, completed, failed, completed_at, run_id),
            )
            await db.commit()

    async def delete_project_run_data(self, project_id: str) -> None:
        """Cascade DELETE: mentions, citations, responses, runs, perception_scores, alerts."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id FROM runs WHERE project_id = ?", (project_id,),
            )
            run_ids = [row["id"] for row in await cursor.fetchall()]

            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                resp_sub = f"SELECT id FROM responses WHERE run_id IN ({placeholders})"
                await db.execute(
                    f"DELETE FROM mentions WHERE response_id IN ({resp_sub})",
                    run_ids,
                )
                await db.execute(
                    f"DELETE FROM citations WHERE response_id IN ({resp_sub})",
                    run_ids,
                )
                await db.execute(
                    f"DELETE FROM responses WHERE run_id IN ({placeholders})", run_ids,
                )
                await db.execute(
                    f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids,
                )

            await db.execute("DELETE FROM perception_scores WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM alerts WHERE project_id = ?", (project_id,))
            await db.commit()

    async def get_aggregate_perception_score(self, project_id: str) -> aiosqlite.Row | None:
        """Latest aggregate score row (term_id IS NULL, provider_name IS NULL)."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT overall_score, recommendation_share FROM perception_scores"
                " WHERE project_id = ? AND term_id IS NULL AND provider_name IS NULL"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            )
            return await cursor.fetchone()

    async def get_competitors_detected(self, run_id: str) -> list[str]:
        """DISTINCT competitor names from mentions JOIN responses for a run."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT DISTINCT m.target_name FROM mentions m"
                " JOIN responses r ON r.id = m.response_id"
                " WHERE r.run_id = ? AND m.mention_type = 'competitor'",
                (run_id,),
            )
            return [row["target_name"] for row in await cursor.fetchall()]

    async def count_runs_for_project(self, project_id: str) -> int:
        """COUNT runs for a project."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM runs WHERE project_id = ?", (project_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
