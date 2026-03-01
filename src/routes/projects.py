"""Project, brand, and competitor endpoints for GeoStorm API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from src.container import project_service
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.schemas import (  # noqa: TC001
    BrandResponse,
    CompetitorResponse,
    CreateCompetitorRequest,
    CreateProjectRequest,
    ProjectCreatedResponse,
    ProjectDetailResponse,
    ProjectResponse,
    UpdateBrandRequest,
    UpdateProjectRequest,
)
from src.services.project_service import clear_and_trigger_monitoring

router = APIRouter(prefix="/api")


@router.get("/projects")
async def list_projects() -> list[ProjectResponse]:
    return await project_service.list_projects()


@router.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest) -> ProjectCreatedResponse:
    return await project_service.create_project(
        name=req.name,
        description=req.description,
        brand_name=req.brand_name,
        brand_aliases=req.brand_aliases,
        brand_description=req.brand_description,
        brand_website=req.brand_website,
    )


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> ProjectDetailResponse:
    project = await get_project_or_404(project_id)
    return await project_service.get_project_detail(project_id, project)


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest) -> ProjectResponse:
    await get_writable_project_or_403(project_id)

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(tz=UTC).isoformat()
    result = await project_service.update_project(project_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> Response:
    await get_writable_project_or_403(project_id)
    await project_service.soft_delete_project(project_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/monitor", status_code=202)
async def trigger_monitoring(project_id: str) -> dict[str, str]:
    await get_writable_project_or_403(project_id)
    result = await clear_and_trigger_monitoring(project_id)
    if result.get("error") == "no_api_key":
        raise HTTPException(
            status_code=400,
            detail="No API key configured. Add your OpenRouter API key in Settings to run monitoring.",
        )
    if result.get("error") == "no_terms":
        raise HTTPException(
            status_code=400,
            detail=(
                "No monitoring terms configured. Monitoring cannot run without at least one term. "
                "Go to your project page, scroll to the Monitoring Terms section, and add terms "
                "describing what users would ask an AI when looking for a tool like yours "
                '(e.g. "best Python web framework" or "top API testing tools"). '
                "Each term is queried across all configured LLM providers during a monitoring run."
            ),
        )
    return result


@router.get("/projects/{project_id}/brand")
async def get_brand(project_id: str) -> BrandResponse:
    await get_project_or_404(project_id)
    brand = await project_service.get_brand(project_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/projects/{project_id}/brand")
async def update_brand(project_id: str, req: UpdateBrandRequest) -> BrandResponse:
    await get_writable_project_or_403(project_id)

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.website is not None:
        updates["website"] = req.website
    if req.aliases is not None:
        updates["aliases_json"] = json.dumps(req.aliases)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(tz=UTC).isoformat()
    brand = await project_service.update_brand(project_id, updates)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.get("/projects/{project_id}/competitors")
async def list_competitors(project_id: str) -> list[CompetitorResponse]:
    await get_project_or_404(project_id)
    return await project_service.list_competitors(project_id)


@router.post("/projects/{project_id}/competitors", status_code=201)
async def create_competitor(project_id: str, req: CreateCompetitorRequest) -> CompetitorResponse:
    await get_writable_project_or_403(project_id)
    return await project_service.create_competitor(
        project_id, req.name, req.aliases, req.website,
    )


@router.delete("/projects/{project_id}/competitors/{competitor_id}")
async def delete_competitor(project_id: str, competitor_id: str) -> Response:
    await get_writable_project_or_403(project_id)
    rowcount = await project_service.delete_competitor(competitor_id, project_id)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return Response(status_code=204)
