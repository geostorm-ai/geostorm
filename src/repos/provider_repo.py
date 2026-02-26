"""Repository for llm_providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class ProviderRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def list_providers(self, project_id: str) -> list[aiosqlite.Row]:
        """Return all providers for a project."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM llm_providers WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            )
            return list(await cursor.fetchall())

    async def list_enabled_providers(self, project_id: str) -> list[aiosqlite.Row]:
        """Return enabled providers (for the scheduler)."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT provider_name, model_name FROM llm_providers WHERE project_id = ? AND is_enabled = 1",
                (project_id,),
            )
            return list(await cursor.fetchall())

    async def find_provider(
        self, project_id: str, provider_name: str, model_name: str,
    ) -> aiosqlite.Row | None:
        """Check for a duplicate provider+model combination."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id FROM llm_providers WHERE project_id = ? AND provider_name = ? AND model_name = ?",
                (project_id, provider_name, model_name),
            )
            return await cursor.fetchone()

    async def create_provider(
        self,
        provider_id: str,
        project_id: str,
        provider_name: str,
        model_name: str,
        now: str,
    ) -> None:
        """Insert a new LLM provider."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO llm_providers"
                " (id, project_id, provider_name, model_name, is_enabled, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?, ?)",
                (provider_id, project_id, provider_name, model_name, now, now),
            )
            await db.commit()

    async def update_provider(
        self, provider_id: str, project_id: str, updates: dict[str, object],
    ) -> tuple[int, aiosqlite.Row | None]:
        """Dynamic UPDATE. Returns (rowcount, refreshed row or None)."""
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = [*list(updates.values()), provider_id, project_id]
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"UPDATE llm_providers SET {set_clause} WHERE id = ? AND project_id = ?",
                values,
            )
            rowcount = cursor.rowcount
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM llm_providers WHERE id = ? AND project_id = ?",
                (provider_id, project_id),
            )
            row = await cursor.fetchone()
        return rowcount, row

    async def delete_provider(self, provider_id: str, project_id: str) -> int:
        """Delete a provider. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM llm_providers WHERE id = ? AND project_id = ?",
                (provider_id, project_id),
            )
            await db.commit()
            return cursor.rowcount
