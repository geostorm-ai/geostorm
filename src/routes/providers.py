"""LLM provider endpoints for GeoStorm API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from src.container import provider_service
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.schemas import (
    CreateProviderRequest,
    LLMProviderResponse,
    UpdateProviderRequest,
)

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/providers")
async def list_providers(project_id: str) -> list[LLMProviderResponse]:
    await get_project_or_404(project_id)
    rows = await provider_service.list_providers(project_id)
    return [
        LLMProviderResponse(
            id=row["id"],
            project_id=row["project_id"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            is_enabled=bool(row["is_enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("/projects/{project_id}/providers", status_code=201)
async def create_provider(project_id: str, body: CreateProviderRequest) -> LLMProviderResponse:
    await get_writable_project_or_403(project_id)
    provider_id = uuid.uuid4().hex
    now = datetime.now(tz=UTC).isoformat()
    existing = await provider_service.create_provider(
        provider_id, project_id, body.provider_name, body.model_name, now,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Provider with this model already exists")
    return LLMProviderResponse(
        id=provider_id,
        project_id=project_id,
        provider_name=body.provider_name,
        model_name=body.model_name,
        is_enabled=True,
        created_at=now,
        updated_at=now,
    )


@router.patch("/projects/{project_id}/providers/{provider_id}")
async def update_provider(
    project_id: str, provider_id: str, body: UpdateProviderRequest,
) -> LLMProviderResponse:
    await get_writable_project_or_403(project_id)

    updates: dict[str, Any] = {}
    if body.is_enabled is not None:
        updates["is_enabled"] = int(body.is_enabled)
    if body.model_name is not None:
        updates["model_name"] = body.model_name

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(tz=UTC).isoformat()
    rowcount, row = await provider_service.update_provider(provider_id, project_id, updates)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")
    return LLMProviderResponse(
        id=row["id"],
        project_id=row["project_id"],
        provider_name=row["provider_name"],
        model_name=row["model_name"],
        is_enabled=bool(row["is_enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/projects/{project_id}/providers/{provider_id}")
async def delete_provider(project_id: str, provider_id: str) -> Response:
    await get_writable_project_or_403(project_id)
    rowcount = await provider_service.delete_provider(provider_id, project_id)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Provider not found")
    return Response(status_code=204)
