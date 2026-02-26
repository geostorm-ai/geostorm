import contextlib
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.routes.runs import router

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


async def _seed_run(db_path, project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, completed_queries,"
            " failed_queries, started_at, completed_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-1", project_id, "completed", "manual", 2, 2, 0, now, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_responses_and_mentions(db_path, run_id="run-1", project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("term-1", project_id, "test term", 1, now, now),
        )
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name, model_name,"
            " response_text, latency_ms, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("resp-1", run_id, project_id, "term-1", "openrouter", "gpt-4", "Some response text", 500, now),
        )
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("mention-1", "resp-1", "competitor", "CompetitorX", now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_perception(db_path, project_id="proj-1"):
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO perception_scores (id, project_id, term_id, provider_name, recommendation_share,"
            " overall_score, trend_direction, period_type, period_start, period_end, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ps-1", project_id, None, None, 0.75, 82.5, "up", "daily", "2024-01-01", "2024-01-01", now),
        )
        await db.commit()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_list_runs(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_run(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_list_runs_filter_status(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_run(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/runs", params={"status": "completed"})
            assert resp.status_code == 200
            data = resp.json()
            for item in data["items"]:
                assert item["status"] == "completed"


@pytest.mark.asyncio
async def test_list_runs_empty(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_get_run_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_run(db_path)
    await _seed_perception(db_path)
    await _seed_responses_and_mentions(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/run-1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "run-1"
            assert "perception_score" in data
            assert "competitors_detected" in data


@pytest.mark.asyncio
async def test_get_run_404(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/nonexistent")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_responses(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_run(db_path)
    await _seed_responses_and_mentions(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/run-1/responses")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) >= 1
            assert "mentions" in data["items"][0]


@pytest.mark.asyncio
async def test_get_perception(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_perception(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/perception")
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["overall_score"] == 82.5
