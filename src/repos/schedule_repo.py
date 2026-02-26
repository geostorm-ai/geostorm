"""Repository for project_schedules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class ScheduleRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def get_schedule(self, project_id: str) -> aiosqlite.Row | None:
        """Return the schedule row for a project, or ``None``."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM project_schedules WHERE project_id = ?",
                (project_id,),
            )
            return await cursor.fetchone()

    async def create_schedule(  # noqa: PLR0913
        self,
        schedule_id: str,
        project_id: str,
        hour_of_day: int,
        days_of_week_json: str,
        is_active: bool,
        now: str,
    ) -> None:
        """Insert a new schedule."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO project_schedules"
                " (id, project_id, hour_of_day, days_of_week_json, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (schedule_id, project_id, hour_of_day, days_of_week_json, is_active, now, now),
            )
            await db.commit()

    async def update_schedule(
        self, project_id: str, set_clauses: list[str], params: list[object],
    ) -> aiosqlite.Row | None:
        """Dynamic UPDATE on the schedule. Returns the refreshed row or ``None``."""
        async with self._get_connection() as db:
            await db.execute(
                f"UPDATE project_schedules SET {', '.join(set_clauses)} WHERE project_id = ?",
                params,
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM project_schedules WHERE project_id = ?",
                (project_id,),
            )
            return await cursor.fetchone()

    async def update_last_run_at(self, schedule_id: str, timestamp: str) -> None:
        """Update last_run_at for a schedule."""
        async with self._get_connection() as db:
            await db.execute(
                "UPDATE project_schedules SET last_run_at = ? WHERE id = ?",
                (timestamp, schedule_id),
            )
            await db.commit()

    async def get_active_schedules(self) -> list[aiosqlite.Row]:
        """Return active schedules joined with non-deleted, non-demo projects."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT ps.id, ps.project_id, ps.hour_of_day, ps.days_of_week_json, ps.last_run_at
                FROM project_schedules ps
                JOIN projects p ON p.id = ps.project_id
                WHERE ps.is_active = 1 AND p.is_demo = 0 AND p.deleted_at IS NULL
                """,
            )
            return list(await cursor.fetchall())
