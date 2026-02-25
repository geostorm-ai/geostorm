"""Tests for the analysis pipeline orchestrator."""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite

from src.services.analysis import analyze_run

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


async def _setup_test_db(db_path: str) -> None:
    """Initialize a test database with schema and seed data."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(schema_sql)
        now = datetime.now(tz=UTC).isoformat()

        # Project
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )
        # Brand
        await db.execute(
            "INSERT INTO brands (id, project_id, name, aliases_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("brand-1", "proj-1", "FastAPI", '["FastAPI Python"]', now, now),
        )
        # Competitors
        await db.execute(
            "INSERT INTO competitors (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("comp-1", "proj-1", "Litestar", 1, now, now),
        )
        await db.execute(
            "INSERT INTO competitors (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("comp-2", "proj-1", "Flask", 1, now, now),
        )
        # Term
        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("term-1", "proj-1", "best Python framework", 1, now, now),
        )
        # Run
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "proj-1", "completed", "manual", 2, now, now),
        )
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name, model_name,"
            " response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "resp-1", "run-1", "proj-1", "term-1", "openrouter", "gpt-4o",
                "Here are the best Python frameworks:\n1. Litestar - Full-featured\n2. FastAPI - Modern async\n"
                "3. Flask - Lightweight",
                now,
            ),
        )
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name, model_name,"
            " response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "resp-2", "run-1", "proj-1", "term-1", "openrouter", "claude-3",
                "Top recommendations:\n1. FastAPI - Best for async\n2. Litestar - Great ORM\n3. Starlette",
                now,
            ),
        )
        # Error response (should be skipped by analysis)
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name, model_name,"
            " response_text, error_message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("resp-err", "run-1", "proj-1", "term-1", "openrouter", "gpt-4o-mini", "", "API error", now),
        )

        await db.commit()
    finally:
        await db.close()


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


class TestAnalyzeRun:
    async def test_full_pipeline(self, tmp_path):
        """End-to-end: mention detection, scoring, and change detection all run."""
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        fake_conn = _fake_db_conn(db_path)

        with (
            patch("src.services.analysis.get_db_connection", side_effect=fake_conn),
            patch("src.services.mention_service.get_db_connection", side_effect=fake_conn),
            patch("src.services.scoring_service.get_db_connection", side_effect=fake_conn),
            patch("src.services.change_detection.get_db_connection", side_effect=fake_conn),
        ):
            await analyze_run("run-1", "proj-1")

        # Verify mentions were created
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM mentions")
            row = await cursor.fetchone()
            assert row["cnt"] > 0

            # Verify perception scores were created
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM perception_scores")
            row = await cursor.fetchone()
            assert row["cnt"] > 0
        finally:
            await db.close()

    async def test_analysis_failure_does_not_fail_run(self, tmp_path):
        """If mention detection raises, analyze_run should NOT propagate the exception."""
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        fake_conn = _fake_db_conn(db_path)
        mock_mentions = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch("src.services.analysis.get_db_connection", side_effect=fake_conn),
            patch(
                "src.services.analysis.detect_and_store_mentions_for_response",
                mock_mentions,
            ),
            patch("src.services.analysis.calculate_and_store_scores", new_callable=AsyncMock),
            patch("src.services.analysis.detect_and_store_alerts", new_callable=AsyncMock),
        ):
            # Should complete without raising
            await analyze_run("run-1", "proj-1")

    async def test_no_brand_graceful_handling(self, tmp_path):
        """When the project has no brand row, analyze_run returns gracefully."""
        db_path = str(tmp_path / "test_no_brand.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.executescript(schema_sql)
            now = datetime.now(tz=UTC).isoformat()
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-nobrand", "No Brand Project", 0, now, now),
            )
            await db.execute(
                "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("run-nb", "proj-nobrand", "completed", "manual", 0, now, now),
            )
            await db.commit()
        finally:
            await db.close()

        fake_conn = _fake_db_conn(db_path)

        with patch("src.services.analysis.get_db_connection", side_effect=fake_conn):
            # Should return without error
            await analyze_run("run-nb", "proj-nobrand")
