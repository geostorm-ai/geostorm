"""Tests for the MCP server tools."""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from src.mcp_server import mcp

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
    """Initialize DB with schema and seed data for MCP tests."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    now = datetime.now(tz=UTC).isoformat()
    try:
        await db.executescript(schema_sql)

        # Project
        await db.execute(
            "INSERT INTO projects (id, name, description, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", "A test project", 0, now, now),
        )

        # Brand
        await db.execute(
            "INSERT INTO brands (id, project_id, name, aliases_json, description, website, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("brand-1", "proj-1", "TestBrand", '["TB"]', "Brand desc", "https://test.com", now, now),
        )

        # Competitor
        await db.execute(
            "INSERT INTO competitors (id, project_id, name, aliases_json, website, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("comp-1", "proj-1", "Competitor A", '[]', None, 1, now, now),
        )

        # Terms
        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, description, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("term-1", "proj-1", "best test tool", None, 1, now, now),
        )

        # Schedule
        await db.execute(
            "INSERT INTO project_schedules"
            " (id, project_id, hour_of_day, days_of_week_json, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sched-1", "proj-1", 14, "[0,1,2,3,4]", 1, now, now),
        )

        # Run
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, completed_queries,"
            " failed_queries, started_at, completed_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "proj-1", "completed", "manual", 2, 2, 0, now, now, now),
        )

        # Perception score
        await db.execute(
            "INSERT INTO perception_scores"
            " (id, project_id, term_id, provider_name, recommendation_share, position_avg,"
            "  competitor_delta, overall_score, trend_direction, period_type, period_start, period_end, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ps-1", "proj-1", None, None, 0.75, 2.0, 0.1, 72.5, "up", "daily", now, now, now),
        )

        # Alert
        await db.execute(
            "INSERT INTO alerts (id, project_id, alert_type, severity, title, message, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("alert-1", "proj-1", "competitor_emergence", "warning", "New competitor", "CompB appeared", now),
        )

        await db.commit()
    finally:
        await db.close()


async def test_list_projects(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("list_projects", {})

    data = result.structured_content
    projects = data.get("result", data)
    assert len(projects) >= 1
    proj = projects[0]
    assert proj["id"] == "proj-1"
    assert proj["name"] == "Test Project"


def _unwrap(data: dict) -> dict:
    """Unwrap FastMCP's {"result": ...} envelope if present."""
    return data.get("result", data) if isinstance(data.get("result"), dict) else data


async def test_get_project_summary_by_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("get_project_summary", {"project": "proj-1"})

    data = _unwrap(result.structured_content)
    assert data["project"]["id"] == "proj-1"
    assert data["project"]["brand"]["name"] == "TestBrand"
    assert data["perception"]["project_id"] == "proj-1"
    assert "by_term" in data["breakdown"]
    assert isinstance(data["recent_runs"], list)
    assert isinstance(data["alerts"], list)


async def test_get_project_summary_by_name(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("get_project_summary", {"project": "test project"})

    data = _unwrap(result.structured_content)
    assert data["project"]["id"] == "proj-1"
    assert data["project"]["name"] == "Test Project"


async def test_get_project_summary_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("get_project_summary", {"project": "nonexistent-xyz"})

    data = _unwrap(result.structured_content)
    assert "error" in data
    assert "available" in data
    assert "Test Project" in data["available"]


async def test_get_run_detail_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("get_run_detail", {"run_id": "nonexistent"})

    data = _unwrap(result.structured_content)
    assert "error" in data


async def test_get_trajectory(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
        result = await mcp.call_tool("get_trajectory", {"project": "proj-1"})

    data = _unwrap(result.structured_content)
    assert data["project_id"] == "proj-1"
    assert "data" in data
