"""CRUD operations for alerts and alert configuration."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.models import (
    Alert,
    AlertChannel,
    AlertConfig,
    AlertMetadata,
    AlertSeverity,
    AlertType,
)

if TYPE_CHECKING:
    import aiosqlite

    from src.repos.alert_repo import AlertRepo

logger = logging.getLogger(__name__)

SEVERITY_ORDER: dict[str, int] = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.CRITICAL: 2,
}


def _row_to_alert(row: aiosqlite.Row) -> Alert:
    """Convert a database row to an Alert model."""
    metadata = None
    if row["metadata_json"]:
        metadata = AlertMetadata.model_validate_json(row["metadata_json"])

    return Alert(
        id=row["id"],
        project_id=row["project_id"],
        alert_type=AlertType(row["alert_type"]),
        severity=AlertSeverity(row["severity"]),
        title=row["title"],
        message=row["message"],
        metadata=metadata,
        explanation=row["explanation"],
        is_acknowledged=bool(row["is_acknowledged"]),
        acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
        acknowledged_by=row["acknowledged_by"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_alert_config(row: aiosqlite.Row) -> AlertConfig:
    """Convert a database row to an AlertConfig model."""
    raw_types = json.loads(row["alert_types_json"]) if row["alert_types_json"] else []
    alert_types = [AlertType(t) for t in raw_types]

    return AlertConfig(
        id=row["id"],
        project_id=row["project_id"],
        channel=AlertChannel(row["channel"]),
        endpoint=row["endpoint"],
        alert_types=alert_types,
        min_severity=AlertSeverity(row["min_severity"]),
        is_enabled=bool(row["is_enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _build_alert_where(
    project_id: str,
    severity: AlertSeverity | None = None,
    acknowledged: bool | None = None,
) -> tuple[str, list[object]]:
    """Build WHERE clause and params for alert queries."""
    clauses = ["project_id = ?"]
    params: list[object] = [project_id]

    if severity is not None:
        min_level = SEVERITY_ORDER[severity]
        allowed = [s for s, level in SEVERITY_ORDER.items() if level >= min_level]
        placeholders = ", ".join("?" for _ in allowed)
        clauses.append(f"severity IN ({placeholders})")
        params.extend(allowed)

    if acknowledged is not None:
        clauses.append("is_acknowledged = ?")
        params.append(1 if acknowledged else 0)

    return " AND ".join(clauses), params


class AlertService:
    def __init__(self, alert_repo: AlertRepo) -> None:
        self._alert_repo = alert_repo

    async def get_alert(self, alert_id: str) -> Alert | None:
        """Fetch a single alert by ID."""
        row = await self._alert_repo.get_alert(alert_id)
        if not row:
            return None
        return _row_to_alert(row)

    async def count_alerts(
        self,
        project_id: str,
        *,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> int:
        """Count alerts for a project with optional filters."""
        where, params = _build_alert_where(project_id, severity, acknowledged)
        return await self._alert_repo.count_alerts(where, params)

    async def list_alerts(
        self,
        project_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        """List alerts for a project with optional filters."""
        where, params = _build_alert_where(project_id, severity, acknowledged)
        rows = await self._alert_repo.list_alerts(limit, offset, where, params)
        return [_row_to_alert(row) for row in rows]

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Mark an alert as acknowledged. Returns True if the alert was found and updated."""
        now = datetime.now(tz=UTC).isoformat()
        rowcount = await self._alert_repo.acknowledge_alert(alert_id, acknowledged_by, now)
        return rowcount > 0

    async def get_alert_configs(self, project_id: str) -> list[AlertConfig]:
        """Get all alert configs for a project."""
        rows = await self._alert_repo.get_alert_configs(project_id)
        return [_row_to_alert_config(row) for row in rows]

    async def upsert_alert_config(  # noqa: PLR0913
        self,
        project_id: str,
        channel: AlertChannel,
        endpoint: str,
        alert_types: list[AlertType],
        min_severity: AlertSeverity = AlertSeverity.INFO,
        is_enabled: bool = True,
    ) -> str:
        """Create or update an alert config. Returns the config ID."""
        now = datetime.now(tz=UTC).isoformat()
        types_json = json.dumps([t.value for t in alert_types])

        existing = await self._alert_repo.find_alert_config(project_id, channel.value, endpoint)

        if existing:
            config_id: str = existing["id"]
            await self._alert_repo.update_alert_config(config_id, types_json, min_severity.value, is_enabled, now)
        else:
            config_id = uuid.uuid4().hex
            await self._alert_repo.insert_alert_config(
                config_id, project_id, channel.value, endpoint,
                types_json, min_severity.value, is_enabled, now,
            )

        return config_id

    async def delete_alert_config(self, config_id: str) -> bool:
        """Delete an alert config. Returns True if the config was found and deleted."""
        return await self._alert_repo.delete_alert_config(config_id) > 0
