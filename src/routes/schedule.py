"""Schedule endpoints for GeoStorm API."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from src.container import schedule_service
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.schemas import ScheduleResponse, UpdateScheduleRequest

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/schedule")
async def get_schedule(project_id: str) -> ScheduleResponse:
    await get_project_or_404(project_id)
    result = await schedule_service.get_schedule(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse(**result)


@router.patch("/projects/{project_id}/schedule")
async def update_schedule(
    project_id: str, body: UpdateScheduleRequest,
) -> ScheduleResponse:
    await get_writable_project_or_403(project_id)

    set_clauses: list[str] = []
    params: list[object] = []

    if body.hour_of_day is not None:
        set_clauses.append("hour_of_day = ?")
        params.append(body.hour_of_day)

    if body.days_of_week is not None:
        set_clauses.append("days_of_week_json = ?")
        params.append(json.dumps(body.days_of_week))

    if body.is_active is not None:
        set_clauses.append("is_active = ?")
        params.append(1 if body.is_active else 0)

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.now(tz=UTC).isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(project_id)

    result = await schedule_service.update_schedule(project_id, set_clauses, params)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return ScheduleResponse(**result)
