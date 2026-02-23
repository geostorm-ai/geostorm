"""Project, brand, and competitor endpoints for GeoStorm API."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from src.database import get_db_connection
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.scheduler import execute_monitoring_run
from src.schemas import (
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

router = APIRouter(prefix="/api")

_background_tasks: set[asyncio.Task[Any]] = set()


@router.get("/projects")
async def list_projects() -> list[ProjectResponse]:
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [ProjectResponse(**dict(row)) for row in rows]


@router.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest) -> ProjectCreatedResponse:
    now = datetime.now(tz=UTC).isoformat()
    project_id = uuid.uuid4().hex
    brand_id = uuid.uuid4().hex
    schedule_id = uuid.uuid4().hex

    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO projects (id, name, description, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, req.name, req.description, False, now, now),
        )
        await db.execute(
            "INSERT INTO brands (id, project_id, name, aliases_json, description, website, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                brand_id,
                project_id,
                req.brand_name,
                json.dumps(req.brand_aliases),
                req.brand_description,
                req.brand_website,
                now,
                now,
            ),
        )
        await db.execute(
            "INSERT INTO project_schedules"
            " (id, project_id, hour_of_day, days_of_week_json, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (schedule_id, project_id, 14, "[0,1,2,3,4]", True, now, now),
        )
        await db.commit()

    return ProjectCreatedResponse(
        id=project_id,
        name=req.name,
        brand_id=brand_id,
        schedule_id=schedule_id,
        created_at=now,
    )


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> ProjectDetailResponse:
    project = await get_project_or_404(project_id)

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM brands WHERE project_id = ?", (project_id,),
        )
        brand_row = await cursor.fetchone()
        brand = None
        if brand_row:
            brand = dict(brand_row)
            brand["aliases"] = (
                json.loads(brand["aliases_json"]) if brand["aliases_json"] else []
            )

        cursor = await db.execute(
            "SELECT * FROM competitors WHERE project_id = ?", (project_id,),
        )
        competitor_rows = await cursor.fetchall()
        competitors = []
        for row in competitor_rows:
            comp = dict(row)
            comp["aliases"] = (
                json.loads(comp["aliases_json"]) if comp["aliases_json"] else []
            )
            competitors.append(comp)

        cursor = await db.execute(
            "SELECT * FROM project_terms WHERE project_id = ?", (project_id,),
        )
        term_rows = await cursor.fetchall()
        terms = [dict(row) for row in term_rows]

        cursor = await db.execute(
            "SELECT * FROM project_schedules WHERE project_id = ?", (project_id,),
        )
        schedule_row = await cursor.fetchone()
        schedule = None
        if schedule_row:
            schedule = dict(schedule_row)
            schedule["days_of_week"] = json.loads(schedule["days_of_week_json"])

    return ProjectDetailResponse(
        **dict(project),
        brand=brand,
        competitors=competitors,
        terms=terms,
        schedule=schedule,
    )


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
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = [*list(updates.values()), project_id]

    async with get_db_connection() as db:
        await db.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?", values,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**dict(row))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> Response:
    await get_writable_project_or_403(project_id)

    now = datetime.now(tz=UTC).isoformat()
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, project_id),
        )
        await db.commit()

    return Response(status_code=204)


@router.post("/projects/{project_id}/monitor", status_code=202)
async def trigger_monitoring(project_id: str) -> dict[str, str]:
    await get_writable_project_or_403(project_id)
    task = asyncio.create_task(execute_monitoring_run(project_id, trigger_type="manual"))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"status": "accepted", "message": "Monitoring run triggered"}


@router.get("/projects/{project_id}/brand")
async def get_brand(project_id: str) -> BrandResponse:
    await get_project_or_404(project_id)

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM brands WHERE project_id = ?", (project_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")

    return BrandResponse(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
        description=row["description"],
        website=row["website"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = [*list(updates.values()), project_id]

    async with get_db_connection() as db:
        await db.execute(
            f"UPDATE brands SET {set_clause} WHERE project_id = ?", values,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM brands WHERE project_id = ?", (project_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")
    return BrandResponse(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
        description=row["description"],
        website=row["website"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/projects/{project_id}/competitors")
async def list_competitors(project_id: str) -> list[CompetitorResponse]:
    await get_project_or_404(project_id)

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM competitors WHERE project_id = ?", (project_id,),
        )
        rows = await cursor.fetchall()

    return [
        CompetitorResponse(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
            website=row["website"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("/projects/{project_id}/competitors", status_code=201)
async def create_competitor(project_id: str, req: CreateCompetitorRequest) -> CompetitorResponse:
    await get_writable_project_or_403(project_id)

    now = datetime.now(tz=UTC).isoformat()
    competitor_id = uuid.uuid4().hex

    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO competitors"
            " (id, project_id, name, aliases_json, website, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (competitor_id, project_id, req.name, json.dumps(req.aliases), req.website, True, now, now),
        )
        await db.commit()

    return CompetitorResponse(
        id=competitor_id,
        project_id=project_id,
        name=req.name,
        aliases=req.aliases,
        website=req.website,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@router.delete("/projects/{project_id}/competitors/{competitor_id}")
async def delete_competitor(project_id: str, competitor_id: str) -> Response:
    await get_writable_project_or_403(project_id)

    async with get_db_connection() as db:
        cursor = await db.execute(
            "DELETE FROM competitors WHERE id = ? AND project_id = ?",
            (competitor_id, project_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Competitor not found")

    return Response(status_code=204)
