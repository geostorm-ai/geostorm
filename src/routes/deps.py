"""Shared route dependencies for GeoStorm API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from src.database import get_db_connection

if TYPE_CHECKING:
    import aiosqlite


async def get_project_or_404(project_id: str) -> aiosqlite.Row:
    """Fetch a project row by ID, raising 404 if not found or soft-deleted."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,),
        )
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return row


async def get_writable_project_or_403(project_id: str) -> aiosqlite.Row:
    """Fetch a project row and raise 403 if it is a demo project."""
    row = await get_project_or_404(project_id)
    if row["is_demo"]:
        raise HTTPException(status_code=403, detail="Demo projects are read-only")
    return row
