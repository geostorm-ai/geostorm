"""Tests for demo project read-only enforcement.

Verifies that:
- Demo project is seeded on first startup
- All write endpoints return 403 for demo projects
- All read endpoints work normally for demo projects
"""

import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.demo_data import DEMO_PROJECT_ID, seed_demo_data
from src.routes.alerts import router as alerts_router
from src.routes.projects import router as projects_router
from src.routes.runs import router as runs_router
from src.routes.schedule import router as schedule_router
from src.routes.terms import router as terms_router

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


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


async def _init_with_demo(db_path: str) -> None:
    """Create schema and seed the full demo project."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.executescript(schema_sql)
        await db.execute("PRAGMA foreign_keys = ON")
        await seed_demo_data(db)
    finally:
        await db.close()


def _build_app():
    test_app = FastAPI()
    test_app.include_router(projects_router)
    test_app.include_router(terms_router)
    test_app.include_router(schedule_router)
    test_app.include_router(alerts_router)
    test_app.include_router(runs_router)
    return test_app


def _patches(fake):
    return (
        patch("src.database.get_db_connection", side_effect=fake),
    )


# --------------------------------------------------------------------------
# Demo project exists after seeding
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_project_exists_in_list(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects")
            assert resp.status_code == 200
            projects = resp.json()
            demo_projects = [p for p in projects if p["is_demo"]]
            assert len(demo_projects) == 1
            assert demo_projects[0]["id"] == DEMO_PROJECT_ID


@pytest.mark.asyncio
async def test_demo_project_has_correct_name(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "GeoStorm Demo: FastAPI"
            assert data["is_demo"] is True


# --------------------------------------------------------------------------
# Read endpoints work for demo project
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_demo_project_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["brand"] is not None
            assert data["brand"]["name"] == "FastAPI"


@pytest.mark.asyncio
async def test_read_demo_brand(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}/brand")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "FastAPI"


@pytest.mark.asyncio
async def test_read_demo_competitors(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}/competitors")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 3
            names = {c["name"] for c in data}
            assert names == {"Litestar", "Flask", "Starlette"}


@pytest.mark.asyncio
async def test_read_demo_terms(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}/terms")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 3


@pytest.mark.asyncio
async def test_read_demo_schedule(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}/schedule")
            assert resp.status_code == 200
            data = resp.json()
            assert data["hour_of_day"] == 2
            assert data["days_of_week"] == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_read_demo_runs(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/projects/{DEMO_PROJECT_ID}/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0


# --------------------------------------------------------------------------
# Write endpoints return 403 for demo project
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_demo_project_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                f"/api/projects/{DEMO_PROJECT_ID}",
                json={"name": "Hacked Name"},
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_monitor_demo_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    mock_monitor = AsyncMock()
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)
        stack.enter_context(
            patch("src.scheduler.execute_monitoring_run", mock_monitor),
        )

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/projects/{DEMO_PROJECT_ID}/monitor")
            assert resp.status_code == 403
            mock_monitor.assert_not_called()


@pytest.mark.asyncio
async def test_update_demo_brand_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/projects/{DEMO_PROJECT_ID}/brand",
                json={"name": "NotFastAPI"},
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_demo_competitor_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/projects/{DEMO_PROJECT_ID}/competitors",
                json={"name": "ShouldFail"},
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_demo_competitor_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        # Get a competitor ID first
        db = await aiosqlite.connect(db_path)
        try:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM competitors WHERE project_id = ? LIMIT 1",
                (DEMO_PROJECT_ID,),
            )
            row = await cursor.fetchone()
            comp_id = row["id"]
        finally:
            await db.close()

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/api/projects/{DEMO_PROJECT_ID}/competitors/{comp_id}",
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_demo_term_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/projects/{DEMO_PROJECT_ID}/terms",
                json={"name": "should not work"},
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_demo_term_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        # Get a term ID
        db = await aiosqlite.connect(db_path)
        try:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM project_terms WHERE project_id = ? LIMIT 1",
                (DEMO_PROJECT_ID,),
            )
            row = await cursor.fetchone()
            term_id = row["id"]
        finally:
            await db.close()

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/api/projects/{DEMO_PROJECT_ID}/terms/{term_id}",
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_demo_schedule_returns_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_with_demo(db_path)

    fake = _fake_db_conn(db_path)
    with contextlib.ExitStack() as stack:
        for p in _patches(fake):
            stack.enter_context(p)

        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                f"/api/projects/{DEMO_PROJECT_ID}/schedule",
                json={"hour_of_day": 12},
            )
            assert resp.status_code == 403


# --------------------------------------------------------------------------
# Demo seeding idempotency
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_demo_data_is_idempotent(tmp_path):
    """Calling seed_demo_data twice should not duplicate data."""
    db_path = str(tmp_path / "test.db")
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.executescript(schema_sql)
        await db.execute("PRAGMA foreign_keys = ON")
        await seed_demo_data(db)
        await seed_demo_data(db)

        cursor = await db.execute("SELECT COUNT(*) FROM projects WHERE is_demo = 1")
        row = await cursor.fetchone()
        assert row[0] == 1
    finally:
        await db.close()
