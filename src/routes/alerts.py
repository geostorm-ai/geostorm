"""Alert endpoints for GeoStorm API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.models import AlertChannel, AlertSeverity
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.schemas import (
    AlertConfigResponse,
    AlertResponse,
    PaginatedResponse,
    UpdateAlertConfigRequest,
)
from src.services.alert_service import (
    acknowledge_alert,
    count_alerts,
    get_alert_configs,
    list_alerts,
    upsert_alert_config,
)

router = APIRouter(prefix="/api")


@router.get("/alerts")
async def get_alerts(
    project_id: str = Query(...),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    severity: AlertSeverity | None = Query(default=None),  # noqa: B008
    acknowledged: bool | None = Query(default=None),
) -> PaginatedResponse[AlertResponse]:
    await get_project_or_404(project_id)

    alerts = await list_alerts(
        project_id,
        limit=limit,
        offset=offset,
        severity=severity,
        acknowledged=acknowledged,
    )

    total = await count_alerts(
        project_id,
        severity=severity,
        acknowledged=acknowledged,
    )

    items = [
        AlertResponse(
            id=a.id,
            project_id=a.project_id,
            alert_type=a.alert_type,
            severity=a.severity,
            title=a.title,
            message=a.message,
            explanation=a.explanation,
            is_acknowledged=a.is_acknowledged,
            acknowledged_at=a.acknowledged_at,
            acknowledged_by=a.acknowledged_by,
            created_at=a.created_at,
        )
        for a in alerts
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def post_acknowledge_alert(alert_id: str) -> dict[str, Any]:
    result = await acknowledge_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged"}


@router.get("/alerts/config")
async def get_alert_config(
    project_id: str = Query(...),
) -> list[AlertConfigResponse]:
    await get_project_or_404(project_id)
    configs = await get_alert_configs(project_id)
    return [
        AlertConfigResponse(
            id=c.id,
            project_id=c.project_id,
            channel=c.channel,
            endpoint=c.endpoint,
            alert_types=c.alert_types,
            min_severity=c.min_severity,
            is_enabled=c.is_enabled,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.patch("/alerts/config")
async def update_alert_config(
    body: UpdateAlertConfigRequest,
    project_id: str = Query(...),
) -> list[AlertConfigResponse]:
    await get_writable_project_or_403(project_id)
    for c in body.configs:
        await upsert_alert_config(
            project_id,
            AlertChannel(c.channel),
            c.endpoint,
            c.alert_types,
            c.min_severity,
            c.is_enabled,
        )
    configs = await get_alert_configs(project_id)
    return [
        AlertConfigResponse(
            id=c.id,
            project_id=c.project_id,
            channel=c.channel,
            endpoint=c.endpoint,
            alert_types=c.alert_types,
            min_severity=c.min_severity,
            is_enabled=c.is_enabled,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]
