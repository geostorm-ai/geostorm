"""Tests for the alerts API routes."""

import contextlib
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.routes.alerts import router

_MIGRATIONS = Path(__file__).resolve().parent.parent.parent / "migrations" / "001_initial_schema.sql"


def _fake_db_conn(db_path: str):
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
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.executescript(schema_sql)
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_alerts(db_path):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        alerts = [
            ("a-1", "proj-1", "competitor_emergence", "critical",
             "Alert 1", "Message 1", None, None, 0, None, None, now),
            ("a-2", "proj-1", "disappearance", "warning",
             "Alert 2", "Message 2", None, None, 0, None, None, now),
            ("a-3", "proj-1", "recommendation_share_drop", "info",
             "Alert 3", "Message 3", None, None, 1, now, "admin", now),
        ]
        await db.executemany(
            "INSERT INTO alerts"
            " (id, project_id, alert_type, severity, title, message, metadata_json,"
            " explanation, is_acknowledged, acknowledged_at, acknowledged_by, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            alerts,
        )
        await db.commit()
    finally:
        await db.close()


def _patches(db_path: str):
    fake = _fake_db_conn(db_path)
    return (
        patch("src.routes.deps.get_db_connection", side_effect=fake),
        patch("src.services.alert_service.get_db_connection", side_effect=fake),
    )


@pytest.mark.asyncio
async def test_list_alerts(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_alerts(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/alerts", params={"project_id": "proj-1"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3
            assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_alerts_filter_severity(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_alerts(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/alerts",
                params={"project_id": "proj-1", "severity": "warning"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # warning filter returns warning + critical (severity >= warning)
            assert data["total"] == 2
            severities = {item["severity"] for item in data["items"]}
            assert "info" not in severities


@pytest.mark.asyncio
async def test_list_alerts_filter_acknowledged(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_alerts(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/alerts",
                params={"project_id": "proj-1", "acknowledged": "false"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            for item in data["items"]:
                assert item["is_acknowledged"] is False


@pytest.mark.asyncio
async def test_acknowledge_alert(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_alerts(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/alerts/a-1/acknowledge")
            assert resp.status_code == 200
            assert resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_acknowledge_missing_alert(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/alerts/nonexistent/acknowledge")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_alert_configs(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/alerts/config",
                params={"project_id": "proj-1"},
            )
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_update_alert_configs(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/alerts/config",
                params={"project_id": "proj-1"},
                json={
                    "configs": [
                        {
                            "channel": "slack",
                            "endpoint": "https://hooks.slack.com/test",
                            "alert_types": ["competitor_emergence"],
                            "min_severity": "warning",
                            "is_enabled": True,
                        },
                    ],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["channel"] == "slack"
