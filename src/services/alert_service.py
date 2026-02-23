"""CRUD operations for alerts and alert configuration."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.database import get_db_connection
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


async def get_alert(alert_id: str) -> Alert | None:
    """Fetch a single alert by ID."""
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = await cursor.fetchone()
    if not row:
        return None
    return _row_to_alert(row)


async def list_alerts(
    project_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    severity: AlertSeverity | None = None,
    acknowledged: bool | None = None,
) -> list[Alert]:
    """List alerts for a project with optional filters."""
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

    where = " AND ".join(clauses)
    query = f"SELECT * FROM alerts WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with get_db_connection() as db:
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
    return [_row_to_alert(row) for row in rows]


async def acknowledge_alert(alert_id: str, acknowledged_by: str = "system") -> bool:
    """Mark an alert as acknowledged. Returns True if the alert was found and updated."""
    now = datetime.now(tz=UTC).isoformat()
    async with get_db_connection() as db:
        cursor = await db.execute(
            "UPDATE alerts SET is_acknowledged = 1, acknowledged_at = ?, acknowledged_by = ? WHERE id = ?",
            (now, acknowledged_by, alert_id),
        )
        await db.commit()
    return cursor.rowcount > 0


async def get_alert_configs(project_id: str) -> list[AlertConfig]:
    """Get all alert configs for a project."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM alert_configs WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        )
        rows = await cursor.fetchall()
    return [_row_to_alert_config(row) for row in rows]


async def upsert_alert_config(  # noqa: PLR0913
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

    async with get_db_connection() as db:
        # Check for existing config with same project + channel + endpoint
        cursor = await db.execute(
            "SELECT id FROM alert_configs"
            " WHERE project_id = ? AND channel = ? AND endpoint = ?",
            (project_id, channel.value, endpoint),
        )
        existing = await cursor.fetchone()

        if existing:
            config_id: str = existing["id"]
            await db.execute(
                "UPDATE alert_configs"
                " SET alert_types_json = ?, min_severity = ?,"
                " is_enabled = ?, updated_at = ?"
                " WHERE id = ?",
                (types_json, min_severity.value, int(is_enabled), now, config_id),
            )
        else:
            config_id = uuid.uuid4().hex
            await db.execute(
                "INSERT INTO alert_configs"
                " (id, project_id, channel, endpoint,"
                "  alert_types_json, min_severity, is_enabled,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    config_id, project_id, channel.value, endpoint,
                    types_json, min_severity.value, int(is_enabled),
                    now, now,
                ),
            )
        await db.commit()

    return config_id


async def delete_alert_config(config_id: str) -> bool:
    """Delete an alert config. Returns True if the config was found and deleted."""
    async with get_db_connection() as db:
        cursor = await db.execute("DELETE FROM alert_configs WHERE id = ?", (config_id,))
        await db.commit()
    return cursor.rowcount > 0


async def get_project_name(project_id: str) -> str:
    """Get the name of a project by ID. Returns 'Unknown Project' if not found."""
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
    if not row:
        return "Unknown Project"
    return str(row["name"])
