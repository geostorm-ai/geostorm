"""Tests for the schedule API routes."""

import contextlib
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.routes.schedule import router

_MIGRATIONS = (
    Path(__file__).resolve().parent.parent.parent / "migrations" / "001_initial_schema.sql"
)


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


async def _seed_demo_project(db_path: str) -> None:
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("demo-1", "Demo", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_schedule(
    db_path: str, project_id: str = "proj-1",
) -> None:
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO project_schedules"
            " (id, project_id, hour_of_day, days_of_week_json,"
            " is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sched-1", project_id, 14, "[0,1,2,3,4]", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


def _patches(db_path: str):
    fake = _fake_db_conn(db_path)
    return (
        patch("src.routes.schedule.get_db_connection", side_effect=fake),
        patch("src.routes.deps.get_db_connection", side_effect=fake),
    )


@pytest.mark.asyncio
async def test_get_schedule(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_schedule(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/schedule")
            assert resp.status_code == 200
            data = resp.json()
            assert data["hour_of_day"] == 14
            assert data["days_of_week"] == [0, 1, 2, 3, 4]
            assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_schedule_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/schedule")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_schedule_project_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/nonexistent/schedule")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_schedule_hour(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_schedule(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/projects/proj-1/schedule",
                json={"hour_of_day": 9},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["hour_of_day"] == 9
            assert data["days_of_week"] == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_update_schedule_days(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_schedule(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/projects/proj-1/schedule",
                json={"days_of_week": [0, 1, 2, 3, 4, 5, 6]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["days_of_week"] == [0, 1, 2, 3, 4, 5, 6]


@pytest.mark.asyncio
async def test_update_schedule_disable(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_schedule(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/projects/proj-1/schedule",
                json={"is_active": False},
            )
            assert resp.status_code == 200
            assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_schedule_empty_body_400(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_schedule(db_path)

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/projects/proj-1/schedule",
                json={},
            )
            assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_schedule_demo_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_demo_project(db_path)
    await _seed_schedule(db_path, project_id="demo-1")

    p1, p2 = _patches(db_path)
    with p1, p2:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/projects/demo-1/schedule",
                json={"hour_of_day": 9},
            )
            assert resp.status_code == 403
