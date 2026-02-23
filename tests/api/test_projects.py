import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.routes.projects import router

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
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_brand(db_path, project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO brands (id, project_id, name, aliases_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("brand-1", project_id, "TestBrand", '["tb"]', now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_schedule(db_path, project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO project_schedules"
            " (id, project_id, hour_of_day, days_of_week_json, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sched-1", project_id, 14, "[0,1,2,3,4]", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_demo_project(db_path):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("demo-1", "Demo", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_competitor(db_path, project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO competitors (id, project_id, name, aliases_json, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("comp-1", project_id, "Competitor1", '[]', 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_list_projects_empty(tmp_path):
    db_path = str(tmp_path / "test.db")
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.executescript(schema_sql)
        await db.commit()
    finally:
        await db.close()

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects")
            assert resp.status_code == 200
            assert resp.json() == []


@pytest.mark.asyncio
async def test_list_projects_seeded(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Project"


@pytest.mark.asyncio
async def test_get_project_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_brand(db_path)
    await _seed_schedule(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "proj-1"
            assert data["brand"] is not None
            assert data["schedule"] is not None


@pytest.mark.asyncio
async def test_get_project_404(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/nonexistent")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_project(tmp_path):
    db_path = str(tmp_path / "test.db")
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.executescript(schema_sql)
        await db.commit()
    finally:
        await db.close()

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/projects", json={"name": "New", "brand_name": "NewBrand"})
            assert resp.status_code == 201
            data = resp.json()
            assert "id" in data
            assert "brand_id" in data
            assert "schedule_id" in data

            resp2 = await client.get("/api/projects")
            assert resp2.status_code == 200
            projects = resp2.json()
            assert len(projects) == 1
            assert projects[0]["name"] == "New"


@pytest.mark.asyncio
async def test_patch_project(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch("/api/projects/proj-1", json={"name": "Updated"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Updated"


@pytest.mark.asyncio
async def test_patch_demo_project_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_demo_project(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch("/api/projects/demo-1", json={"name": "Updated"})
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_monitor(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    mock_monitor = AsyncMock()
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake), \
         patch("src.routes.projects.execute_monitoring_run", mock_monitor):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/projects/proj-1/monitor")
            assert resp.status_code == 202


@pytest.mark.asyncio
async def test_get_brand(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_brand(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/brand")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "TestBrand"


@pytest.mark.asyncio
async def test_update_brand(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_brand(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put("/api/projects/proj-1/brand", json={"name": "Updated Brand"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Updated Brand"


@pytest.mark.asyncio
async def test_list_competitors(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_competitor(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/competitors")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1


@pytest.mark.asyncio
async def test_create_competitor(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/competitors",
                json={"name": "NewCompetitor"},
            )
            assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_competitor(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_competitor(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/projects/proj-1/competitors/comp-1")
            assert resp.status_code == 204


@pytest.mark.asyncio
async def test_demo_write_protection(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_demo_project(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.routes.projects.get_db_connection", side_effect=fake), \
         patch("src.routes.deps.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/demo-1/competitors",
                json={"name": "ShouldFail"},
            )
            assert resp.status_code == 403
