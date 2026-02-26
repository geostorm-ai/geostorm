"""Service layer for project schedules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos.schedule_repo import ScheduleRepo


def _parse_schedule(row: aiosqlite.Row) -> dict[str, object]:
    """Convert a schedule row, parsing days_of_week_json."""
    d = dict(row)
    d["days_of_week"] = json.loads(d["days_of_week_json"])
    return d


class ScheduleService:
    def __init__(self, schedule_repo: ScheduleRepo) -> None:
        self._schedule_repo = schedule_repo

    async def get_schedule(self, project_id: str) -> dict[str, object] | None:
        """Return parsed schedule dict or None."""
        row = await self._schedule_repo.get_schedule(project_id)
        if not row:
            return None
        return _parse_schedule(row)

    async def update_schedule(
        self, project_id: str, set_clauses: list[str], params: list[object],
    ) -> dict[str, object] | None:
        """Update schedule and return parsed result."""
        row = await self._schedule_repo.update_schedule(project_id, set_clauses, params)
        if not row:
            return None
        return _parse_schedule(row)
