"""Repository for projects, brands, and competitors."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class ProjectRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def list_projects(self) -> list[aiosqlite.Row]:
        """SELECT projects with subqueries for latest_score, run_count, alert_count."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT p.*,
                    (SELECT ps.overall_score
                     FROM perception_scores ps
                     WHERE ps.project_id = p.id
                       AND ps.term_id IS NULL
                       AND ps.provider_name IS NULL
                     ORDER BY ps.created_at DESC LIMIT 1) as latest_score,
                    (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) as run_count,
                    (SELECT COUNT(*) FROM alerts a
                     WHERE a.project_id = p.id AND a.is_acknowledged = 0) as active_alert_count
                FROM projects p
                WHERE p.deleted_at IS NULL
                ORDER BY p.created_at DESC
                """,
            )
            return list(await cursor.fetchall())

    async def get_project(self, project_id: str) -> aiosqlite.Row | None:
        """SELECT by id, excluding soft-deleted."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE id = ? AND deleted_at IS NULL",
                (project_id,),
            )
            return await cursor.fetchone()

    async def get_project_name(self, project_id: str) -> str:
        """Return the project name, or 'Unknown Project' if not found."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT name FROM projects WHERE id = ?", (project_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return "Unknown Project"
        return str(row["name"])

    async def create_project(
        self, project_id: str, name: str, description: str | None, is_demo: bool, now: str,
    ) -> None:
        """INSERT a new project."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO projects (id, name, description, is_demo, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, name, description, is_demo, now, now),
            )
            await db.commit()

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> aiosqlite.Row | None:
        """Dynamic UPDATE. Returns refreshed row."""
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = [*list(updates.values()), project_id]
        async with self._get_connection() as db:
            await db.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ?", values,
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            return await cursor.fetchone()

    async def soft_delete_project(self, project_id: str, now: str) -> None:
        """SET deleted_at on a project."""
        async with self._get_connection() as db:
            await db.execute(
                "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, project_id),
            )
            await db.commit()

    async def count_non_demo_projects(self) -> int:
        """COUNT projects where is_demo=0."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM projects WHERE is_demo = 0",
            )
            row = await cursor.fetchone()
            return int(row["count"]) if row else 0

    # --- Brands ---

    async def get_brand(self, project_id: str) -> aiosqlite.Row | None:
        """SELECT brand by project_id."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM brands WHERE project_id = ?", (project_id,),
            )
            return await cursor.fetchone()

    async def get_brand_with_aliases(self, project_id: str) -> tuple[str, list[str]] | None:
        """Return (name, aliases list) for the analysis pipeline. None if not found."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT name, aliases_json FROM brands WHERE project_id = ?",
                (project_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return str(row["name"]), json.loads(row["aliases_json"]) if row["aliases_json"] else []

    async def create_brand(  # noqa: PLR0913
        self,
        brand_id: str,
        project_id: str,
        name: str,
        aliases_json: str,
        description: str | None,
        website: str | None,
        now: str,
    ) -> None:
        """INSERT a new brand."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO brands (id, project_id, name, aliases_json, description, website, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (brand_id, project_id, name, aliases_json, description, website, now, now),
            )
            await db.commit()

    async def update_brand(self, project_id: str, updates: dict[str, Any]) -> aiosqlite.Row | None:
        """Dynamic UPDATE. Returns refreshed row."""
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = [*list(updates.values()), project_id]
        async with self._get_connection() as db:
            await db.execute(
                f"UPDATE brands SET {set_clause} WHERE project_id = ?", values,
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM brands WHERE project_id = ?", (project_id,),
            )
            return await cursor.fetchone()

    # --- Competitors ---

    async def list_competitors(self, project_id: str) -> list[aiosqlite.Row]:
        """SELECT competitors for a project."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM competitors WHERE project_id = ?", (project_id,),
            )
            return list(await cursor.fetchall())

    async def list_active_competitor_names(self, project_id: str) -> list[str]:
        """Return names of active competitors for the analysis pipeline."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT name FROM competitors WHERE project_id = ? AND is_active = 1",
                (project_id,),
            )
            return [row["name"] for row in await cursor.fetchall()]

    async def create_competitor(  # noqa: PLR0913
        self,
        competitor_id: str,
        project_id: str,
        name: str,
        aliases_json: str,
        website: str | None,
        now: str,
    ) -> None:
        """INSERT a new competitor."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO competitors"
                " (id, project_id, name, aliases_json, website, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (competitor_id, project_id, name, aliases_json, website, True, now, now),
            )
            await db.commit()

    async def delete_competitor(self, competitor_id: str, project_id: str) -> int:
        """DELETE a competitor. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM competitors WHERE id = ? AND project_id = ?",
                (competitor_id, project_id),
            )
            await db.commit()
            return cursor.rowcount
