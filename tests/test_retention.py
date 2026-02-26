import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.retention import cleanup_old_responses

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


async def _init_db(db_path: str) -> str:
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    project_id = "proj-ret"
    run_id = "run-ret"
    try:
        await db.executescript(schema_sql)
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, "Retention Test", 0, now, now),
        )
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, project_id, "completed", "manual", 2, now),
        )
        await db.commit()
    finally:
        await db.close()
    return run_id


async def _insert_response(db_path: str, run_id: str, created_at: str, error: str | None = None):
    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name, model_name,"
            " response_text, error_message, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, run_id, "proj-ret", "term-1", "openrouter", "gpt-4o",
             "some response text", error, created_at),
        )
        await db.commit()
    finally:
        await db.close()


def _fake_db_conn(db_path: str):
    import contextlib

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


@pytest.mark.asyncio
async def test_cleanup_clears_old_response_text(tmp_path):
    db_path = str(tmp_path / "test.db")
    run_id = await _init_db(db_path)

    old_date = (datetime.now(tz=UTC) - timedelta(days=45)).isoformat()
    recent_date = (datetime.now(tz=UTC) - timedelta(days=5)).isoformat()

    await _insert_response(db_path, run_id, old_date)
    await _insert_response(db_path, run_id, old_date)
    await _insert_response(db_path, run_id, recent_date)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        cleaned = await cleanup_old_responses(retention_days=30)

    assert cleaned == 2

    # Rows are preserved (not deleted) so mentions/citations stay intact
    db = await aiosqlite.connect(db_path)
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM responses")
        row = await cursor.fetchone()
        assert row[0] == 3

        cursor = await db.execute("SELECT response_text FROM responses WHERE created_at < ?", (recent_date,))
        old_rows = await cursor.fetchall()
        for r in old_rows:
            assert r[0] == ""

        cursor = await db.execute("SELECT response_text FROM responses WHERE created_at >= ?", (recent_date,))
        recent_rows = await cursor.fetchall()
        for r in recent_rows:
            assert r[0] == "some response text"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_cleanup_skips_error_responses(tmp_path):
    db_path = str(tmp_path / "test.db")
    run_id = await _init_db(db_path)

    old_date = (datetime.now(tz=UTC) - timedelta(days=45)).isoformat()
    await _insert_response(db_path, run_id, old_date, error="API error")

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        cleaned = await cleanup_old_responses(retention_days=30)

    assert cleaned == 0


@pytest.mark.asyncio
async def test_cleanup_no_old_data(tmp_path):
    db_path = str(tmp_path / "test.db")
    run_id = await _init_db(db_path)

    recent_date = (datetime.now(tz=UTC) - timedelta(days=5)).isoformat()
    await _insert_response(db_path, run_id, recent_date)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        cleaned = await cleanup_old_responses(retention_days=30)

    assert cleaned == 0


@pytest.mark.asyncio
async def test_cleanup_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    run_id = await _init_db(db_path)

    old_date = (datetime.now(tz=UTC) - timedelta(days=45)).isoformat()
    await _insert_response(db_path, run_id, old_date)

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        first_run = await cleanup_old_responses(retention_days=30)
    assert first_run == 1

    fake = _fake_db_conn(db_path)
    with patch("src.database.get_db_connection", side_effect=fake):
        second_run = await cleanup_old_responses(retention_days=30)
    assert second_run == 0
