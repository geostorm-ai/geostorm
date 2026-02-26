"""Repository for alerts and alert_configs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection


class AlertRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def get_alert(self, alert_id: str) -> aiosqlite.Row | None:
        """Fetch a single alert by ID."""
        async with self._get_connection() as db:
            cursor = await db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
            return await cursor.fetchone()

    async def count_alerts(
        self, where_clause: str, params: list[object],
    ) -> int:
        """COUNT alerts with a pre-built WHERE clause."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM alerts WHERE {where_clause}", params,
            )
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def list_alerts(
        self,
        limit: int,
        offset: int,
        where_clause: str,
        params: list[object],
    ) -> list[aiosqlite.Row]:
        """SELECT alerts with pagination and a pre-built WHERE clause."""
        query = f"SELECT * FROM alerts WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        full_params = [*params, limit, offset]
        async with self._get_connection() as db:
            cursor = await db.execute(query, full_params)
            return list(await cursor.fetchall())

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str, now: str) -> int:
        """Mark an alert as acknowledged. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "UPDATE alerts SET is_acknowledged = 1, acknowledged_at = ?, acknowledged_by = ? WHERE id = ?",
                (now, acknowledged_by, alert_id),
            )
            await db.commit()
            return cursor.rowcount

    async def get_alert_configs(self, project_id: str) -> list[aiosqlite.Row]:
        """Return all alert configs for a project."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM alert_configs WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            )
            return list(await cursor.fetchall())

    async def find_alert_config(
        self, project_id: str, channel: str, endpoint: str,
    ) -> aiosqlite.Row | None:
        """Find an existing config for upsert check."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id FROM alert_configs WHERE project_id = ? AND channel = ? AND endpoint = ?",
                (project_id, channel, endpoint),
            )
            return await cursor.fetchone()

    async def insert_alert_config(  # noqa: PLR0913
        self,
        config_id: str,
        project_id: str,
        channel: str,
        endpoint: str,
        types_json: str,
        min_severity: str,
        is_enabled: bool,
        now: str,
    ) -> None:
        """Insert a new alert config."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT INTO alert_configs"
                " (id, project_id, channel, endpoint, alert_types_json,"
                " min_severity, is_enabled, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (config_id, project_id, channel, endpoint, types_json, min_severity, int(is_enabled), now, now),
            )
            await db.commit()

    async def update_alert_config(
        self, config_id: str, types_json: str, min_severity: str, is_enabled: bool, now: str,
    ) -> None:
        """Update an existing alert config."""
        async with self._get_connection() as db:
            await db.execute(
                "UPDATE alert_configs SET alert_types_json = ?, min_severity = ?, is_enabled = ?, updated_at = ?"
                " WHERE id = ?",
                (types_json, min_severity, int(is_enabled), now, config_id),
            )
            await db.commit()

    async def delete_alert_config(self, config_id: str) -> int:
        """Delete an alert config. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute("DELETE FROM alert_configs WHERE id = ?", (config_id,))
            await db.commit()
            return cursor.rowcount

    async def store_alerts(
        self,
        alerts_data: list[tuple[str, str, str, str, str, str]],
    ) -> list[str]:
        """Batch INSERT alerts.

        Each tuple: (project_id, alert_type, severity, title, message, metadata_json).
        Returns list of alert IDs.
        """
        if not alerts_data:
            return []

        ids: list[str] = []
        now = datetime.now(tz=UTC).isoformat()
        async with self._get_connection() as db:
            for project_id, alert_type, severity, title, message, metadata_json in alerts_data:
                alert_id = uuid.uuid4().hex
                await db.execute(
                    "INSERT INTO alerts"
                    " (id, project_id, alert_type, severity, title, message,"
                    " metadata_json, is_acknowledged, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (alert_id, project_id, alert_type, severity, title, message, metadata_json, 0, now),
                )
                ids.append(alert_id)
            await db.commit()
        return ids
