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


async def _seed_perception_breakdown(db_path, project_id="proj-1"):
    """Seed per-term and per-provider perception scores for breakdown tests."""
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        # Per-term score (term_id set, provider_name NULL)
        await db.execute(
            "INSERT INTO perception_scores (id, project_id, term_id, provider_name, recommendation_share,"
            " position_avg, overall_score, trend_direction, period_type, period_start, period_end, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ps-term-1", project_id, "term-1", None, 0.6, 2.0, 70.0, "stable", "daily", "2024-01-01", "2024-01-01", now),
        )
        # Per-provider score (term_id NULL, provider_name set)
        await db.execute(
            "INSERT INTO perception_scores (id, project_id, term_id, provider_name, recommendation_share,"
            " position_avg, overall_score, trend_direction, period_type, period_start, period_end, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ps-prov-1", project_id, None, "openrouter", 0.4, 3.0, 60.0, "stable", "daily", "2024-01-01", "2024-01-01", now),
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


@pytest.mark.asyncio
async def test_get_perception_breakdown(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_run(db_path)
    await _seed_responses_and_mentions(db_path)
    await _seed_perception(db_path)
    await _seed_perception_breakdown(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/perception/breakdown")
            assert resp.status_code == 200
            data = resp.json()
            assert data["project_id"] == "proj-1"
            assert "total_responses" in data
            assert "brand_mentions" in data
            assert len(data["by_term"]) == 1
            assert data["by_term"][0]["term_name"] == "test term"
            assert data["by_term"][0]["recommendation_share"] == 0.6
            assert data["by_term"][0]["position_avg"] == 2.0
            assert len(data["by_provider"]) == 1
            assert data["by_provider"][0]["provider_name"] == "openrouter"
            assert data["by_provider"][0]["recommendation_share"] == 0.4


@pytest.mark.asyncio
async def test_get_perception_breakdown_empty(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/perception/breakdown")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_responses"] == 0
            assert data["brand_mentions"] == 0
            assert data["by_term"] == []
            assert data["by_provider"] == []
