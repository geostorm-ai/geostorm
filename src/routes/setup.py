"""Setup and settings endpoints for GeoStorm API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response

from src.config import get_settings
from src.database import get_db_connection
from src.schemas import ApiKeyStatusResponse, SetupStatusResponse, StoreApiKeyRequest

router = APIRouter(prefix="/api")


@router.get("/setup/status")
async def get_setup_status() -> SetupStatusResponse:
    has_api_key = False

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'openrouter_api_key'",
        )
        row = await cursor.fetchone()
        if row and row["value"]:
            has_api_key = True

    if not has_api_key:
        settings = get_settings()
        if settings.openrouter_api_key:
            has_api_key = True

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM projects WHERE is_demo = 0",
        )
        count_row = await cursor.fetchone()
        project_count: int = count_row["count"] if count_row else 0

    return SetupStatusResponse(
        has_api_key=has_api_key,
        has_projects=project_count > 0,
        project_count=project_count,
    )


@router.get("/settings/api-key-status")
async def get_api_key_status() -> ApiKeyStatusResponse:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'openrouter_api_key'",
        )
        row = await cursor.fetchone()
        if row and row["value"]:
            return ApiKeyStatusResponse(configured=True, source="database")

    settings = get_settings()
    if settings.openrouter_api_key:
        return ApiKeyStatusResponse(configured=True, source="environment")

    return ApiKeyStatusResponse(configured=False, source=None)


@router.post("/settings/api-key")
async def store_api_key(req: StoreApiKeyRequest) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat()

    async with get_db_connection() as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('openrouter_api_key', ?, ?)",
            (req.key, now),
        )
        await db.commit()

    return {"status": "stored"}


@router.delete("/settings/api-key")
async def delete_api_key() -> Response:
    async with get_db_connection() as db:
        await db.execute("DELETE FROM settings WHERE key = 'openrouter_api_key'")
        await db.commit()

    return Response(status_code=204)
