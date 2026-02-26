"""Tests for the alert service CRUD operations."""

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from src.container import alert_service
from src.models import AlertChannel, AlertSeverity, AlertType

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


def _fake_db_conn(db_path: str):
    """Create an async context manager that returns a real aiosqlite connection to db_path."""

    @contextlib.asynccontextmanager
    async def _ctx():
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row
            yield db
        finally:
            await db.close()

    return _ctx


async def _init_db(db_path: str) -> None:
    """Initialize DB with schema and a test project."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    now = datetime.now(tz=UTC).isoformat()
    try:
        await db.executescript(schema_sql)
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_alerts(db_path: str) -> None:
    """Insert sample alerts for testing list/filter operations."""
    db = await aiosqlite.connect(db_path)
    now = datetime.now(tz=UTC).isoformat()
    try:
        cols = (
            "id, project_id, alert_type, severity, title, message,"
            " metadata_json, explanation, is_acknowledged,"
            " acknowledged_at, acknowledged_by, created_at"
        )
        alerts = [
            ("a-1", "proj-1", "competitor_emergence", "critical",
             "Alert 1", "Message 1", None, None, 0, None, None, now),
            ("a-2", "proj-1", "disappearance", "warning",
             "Alert 2", "Message 2", None, None, 0, None, None, now),
            ("a-3", "proj-1", "recommendation_share_drop", "info",
             "Alert 3", "Message 3", None, None, 1, now, "admin", now),
            ("a-4", "proj-1", "position_degradation", "warning",
             "Alert 4", "Message 4", None, None, 0, None, None, now),
            ("a-5", "proj-1", "model_divergence", "critical",
             "Alert 5", "Message 5", None, None, 1, now, "user1", now),
        ]
        await db.executemany(
            f"INSERT INTO alerts ({cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            alerts,
        )
        await db.commit()
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# get_alert tests
# ---------------------------------------------------------------------------


class TestGetAlert:
    async def test_returns_alert_by_id(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alert = await alert_service.get_alert("a-1")

        assert alert is not None
        assert alert.id == "a-1"
        assert alert.alert_type == AlertType.COMPETITOR_EMERGENCE
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.title == "Alert 1"

    async def test_returns_none_for_missing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alert = await alert_service.get_alert("nonexistent")

        assert alert is None


# ---------------------------------------------------------------------------
# list_alerts tests
# ---------------------------------------------------------------------------


class TestListAlerts:
    async def test_returns_all_for_project(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1")

        assert len(alerts) == 5

    async def test_filter_by_severity_warning(self, tmp_path):
        """Filtering by WARNING should return WARNING + CRITICAL alerts."""
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1", severity=AlertSeverity.WARNING)

        # Expect 4: two critical + two warning alerts
        assert len(alerts) == 4
        severities = {a.severity for a in alerts}
        assert AlertSeverity.INFO not in severities

    async def test_filter_by_severity_critical(self, tmp_path):
        """Filtering by CRITICAL should return only CRITICAL alerts."""
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1", severity=AlertSeverity.CRITICAL)

        assert len(alerts) == 2
        assert all(a.severity == AlertSeverity.CRITICAL for a in alerts)

    async def test_filter_acknowledged_true(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1", acknowledged=True)

        assert len(alerts) == 2
        assert all(a.is_acknowledged for a in alerts)

    async def test_filter_acknowledged_false(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1", acknowledged=False)

        assert len(alerts) == 3
        assert all(not a.is_acknowledged for a in alerts)

    async def test_limit_and_offset(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-1", limit=2, offset=0)

        assert len(alerts) == 2

    async def test_empty_for_unknown_project(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            alerts = await alert_service.list_alerts("proj-unknown")

        assert alerts == []


# ---------------------------------------------------------------------------
# acknowledge_alert tests
# ---------------------------------------------------------------------------


class TestAcknowledgeAlert:
    async def test_marks_alert_acknowledged(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)
        await _seed_alerts(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            result = await alert_service.acknowledge_alert("a-1", acknowledged_by="test-user")

        assert result is True

        # Verify in DB
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM alerts WHERE id = ?", ("a-1",))
            row = await cursor.fetchone()
            assert row["is_acknowledged"] == 1
            assert row["acknowledged_by"] == "test-user"
            assert row["acknowledged_at"] is not None
        finally:
            await db.close()

    async def test_returns_false_for_missing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            result = await alert_service.acknowledge_alert("nonexistent")

        assert result is False


# ---------------------------------------------------------------------------
# alert_config CRUD tests
# ---------------------------------------------------------------------------


class TestAlertConfigCrud:
    async def test_upsert_creates_new_config(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            config_id = await alert_service.upsert_alert_config(
                project_id="proj-1",
                channel=AlertChannel.SLACK,
                endpoint="https://hooks.slack.com/test",
                alert_types=[AlertType.COMPETITOR_EMERGENCE],
                min_severity=AlertSeverity.WARNING,
                is_enabled=True,
            )

        assert config_id is not None

        # Verify stored correctly
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM alert_configs WHERE id = ?", (config_id,))
            row = await cursor.fetchone()
            assert row["channel"] == "slack"
            assert row["endpoint"] == "https://hooks.slack.com/test"
            assert row["min_severity"] == "warning"
            types = json.loads(row["alert_types_json"])
            assert types == ["competitor_emergence"]
        finally:
            await db.close()

    async def test_upsert_updates_existing_config(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            config_id1 = await alert_service.upsert_alert_config(
                project_id="proj-1",
                channel=AlertChannel.SLACK,
                endpoint="https://hooks.slack.com/test",
                alert_types=[],
                min_severity=AlertSeverity.INFO,
            )
            # Same project+channel+endpoint -> should update, not create
            config_id2 = await alert_service.upsert_alert_config(
                project_id="proj-1",
                channel=AlertChannel.SLACK,
                endpoint="https://hooks.slack.com/test",
                alert_types=[AlertType.DISAPPEARANCE],
                min_severity=AlertSeverity.CRITICAL,
            )

        assert config_id1 == config_id2

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM alert_configs WHERE id = ?", (config_id2,))
            row = await cursor.fetchone()
            assert row["min_severity"] == "critical"
            types = json.loads(row["alert_types_json"])
            assert types == ["disappearance"]
        finally:
            await db.close()

    async def test_get_configs_returns_all_for_project(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            await alert_service.upsert_alert_config("proj-1", AlertChannel.SLACK, "https://slack.test", [])
            await alert_service.upsert_alert_config("proj-1", AlertChannel.EMAIL, "user@test.com", [])
            configs = await alert_service.get_alert_configs("proj-1")

        assert len(configs) == 2
        channels = {c.channel for c in configs}
        assert channels == {AlertChannel.SLACK, AlertChannel.EMAIL}

    async def test_get_configs_empty_for_unknown_project(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            configs = await alert_service.get_alert_configs("proj-unknown")

        assert configs == []

    async def test_delete_config_removes_entry(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            config_id = await alert_service.upsert_alert_config("proj-1", AlertChannel.WEBHOOK, "https://wh.test", [])
            result = await alert_service.delete_alert_config(config_id)

        assert result is True

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM alert_configs WHERE id = ?", (config_id,))
            row = await cursor.fetchone()
            assert row is None
        finally:
            await db.close()

    async def test_delete_config_returns_false_for_missing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _init_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            result = await alert_service.delete_alert_config("nonexistent")

        assert result is False
