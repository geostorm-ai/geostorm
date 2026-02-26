"""Repository for project_terms."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class TermRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def list_terms(self, project_id: str) -> list[aiosqlite.Row]:
        """Return all active terms for a project."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM project_terms WHERE project_id = ? AND is_active = 1",
                (project_id,),
            )
            return list(await cursor.fetchall())

    async def list_active_term_ids_and_names(self, project_id: str) -> list[aiosqlite.Row]:
        """Return (id, name) for active terms — used by the scheduler."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id, name FROM project_terms WHERE project_id = ? AND is_active = 1",
                (project_id,),
            )
            return list(await cursor.fetchall())

    async def create_term(
        self, term_id: str, project_id: str, name: str, description: str | None, now: str,
    ) -> None:
        """Insert a new term."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO project_terms (id, project_id, name, description, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?, ?)",
                (term_id, project_id, name, description, now, now),
            )
            await db.commit()

    async def delete_term(self, term_id: str, project_id: str) -> int:
        """Delete a term. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM project_terms WHERE id = ? AND project_id = ?",
                (term_id, project_id),
            )
            await db.commit()
            return cursor.rowcount
