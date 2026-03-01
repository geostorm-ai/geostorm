"""Tests for the scheduling loop and run execution."""

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite

from src.llm.base import LLMError, PromptResponse, ProviderType
from src.scheduler import execute_monitoring_run, should_run_schedule

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


# ---------------------------------------------------------------------------
# should_run_schedule tests
# ---------------------------------------------------------------------------


def _make_schedule(
    hour: int = 14,
    days: list[int] | None = None,
    last_run_at: str | None = None,
) -> dict[str, object]:
    """Create a dict that mimics an aiosqlite.Row for testing."""
    if days is None:
        days = [0, 1, 2, 3, 4]
    return {
        "id": "sched-1",
        "project_id": "proj-1",
        "hour_of_day": hour,
        "days_of_week_json": json.dumps(days),
        "last_run_at": last_run_at,
    }


class TestShouldRunSchedule:
    def test_correct_hour_and_day(self):
        # Monday at 14:00 UTC, schedule is for hour 14, Mon-Fri
        schedule = _make_schedule(hour=14, days=[0, 1, 2, 3, 4])
        current_time = datetime(2026, 2, 23, 14, 30, 0, tzinfo=UTC)  # Monday
        assert should_run_schedule(schedule, current_time) is True

    def test_wrong_hour(self):
        schedule = _make_schedule(hour=14, days=[0, 1, 2, 3, 4])
        current_time = datetime(2026, 2, 23, 10, 30, 0, tzinfo=UTC)  # Monday, 10 AM
        assert should_run_schedule(schedule, current_time) is False

    def test_wrong_day(self):
        schedule = _make_schedule(hour=14, days=[0, 1, 2, 3, 4])  # Mon-Fri only
        current_time = datetime(2026, 2, 28, 14, 30, 0, tzinfo=UTC)  # Saturday
        assert should_run_schedule(schedule, current_time) is False

    def test_already_ran_this_hour(self):
        schedule = _make_schedule(
            hour=14,
            days=[0, 1, 2, 3, 4],
            last_run_at="2026-02-23T14:05:00",
        )
        current_time = datetime(2026, 2, 23, 14, 30, 0, tzinfo=UTC)
        assert should_run_schedule(schedule, current_time) is False

    def test_ran_in_different_hour(self):
        schedule = _make_schedule(
            hour=14,
            days=[0, 1, 2, 3, 4],
            last_run_at="2026-02-23T13:05:00",
        )
        current_time = datetime(2026, 2, 23, 14, 30, 0, tzinfo=UTC)
        assert should_run_schedule(schedule, current_time) is True

    def test_weekend_schedule(self):
        schedule = _make_schedule(hour=10, days=[5, 6])  # Sat, Sun
        current_time = datetime(2026, 2, 28, 10, 0, 0, tzinfo=UTC)  # Saturday
        assert should_run_schedule(schedule, current_time) is True

    def test_no_last_run(self):
        schedule = _make_schedule(hour=14, days=[0, 1, 2, 3, 4], last_run_at=None)
        current_time = datetime(2026, 2, 23, 14, 0, 0, tzinfo=UTC)
        assert should_run_schedule(schedule, current_time) is True


# ---------------------------------------------------------------------------
# execute_monitoring_run tests
# ---------------------------------------------------------------------------


async def _setup_test_db(db_path: str) -> None:
    """Initialize a test database with schema and seed data."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(schema_sql)

        now = datetime.now(tz=UTC).isoformat()

        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )

        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("term-1", "proj-1", "best web framework", 1, now, now),
        )
        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("term-2", "proj-1", "fastest Python framework", 1, now, now),
        )

        await db.execute(
            "INSERT INTO llm_providers"
            " (id, project_id, provider_name, model_name, is_enabled, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("prov-1", "proj-1", "openrouter", "openai/gpt-4o", 1, now, now),
        )

        await db.execute(
            "INSERT INTO project_schedules"
            " (id, project_id, hour_of_day, days_of_week_json, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sched-1", "proj-1", 14, "[0,1,2,3,4]", 1, now, now),
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


def _mock_send_prompt(response_text: str = "Mock recommendation list") -> AsyncMock:
    """Create a mock for send_prompt that returns a PromptResponse."""
    return AsyncMock(return_value=PromptResponse(
        text=response_text,
        model_id="openai/gpt-4o",
        provider=ProviderType.OPENROUTER,
        prompt_tokens=50,
        completion_tokens=100,
        total_tokens=150,
        latency_ms=500,
        cost_usd=0.01,
    ))


class TestExecuteMonitoringRun:
    async def test_creates_run_and_responses(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        mock_prompt = _mock_send_prompt()

        with (
            patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)),
            patch("src.scheduler.send_prompt", mock_prompt),
            patch("src.scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            run_id = await execute_monitoring_run(
                project_id="proj-1",
                schedule_id="sched-1",
                trigger_type="manual",
            )

        assert run_id is not None
        assert len(run_id) > 0

        # Verify run record was created
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            run = await cursor.fetchone()
            assert run is not None
            assert run["status"] == "completed"
            assert run["completed_queries"] == 2
            assert run["failed_queries"] == 0
            assert run["total_queries"] == 2

            cursor = await db.execute("SELECT * FROM responses WHERE run_id = ?", (run_id,))
            responses = await cursor.fetchall()
            assert len(responses) == 2
            for resp in responses:
                assert resp["response_text"] == "Mock recommendation list"
                assert resp["error_message"] is None

            cursor = await db.execute(
                "SELECT last_run_at FROM project_schedules WHERE id = ?", ("sched-1",),
            )
            sched = await cursor.fetchone()
            assert sched is not None
            assert sched["last_run_at"] is not None
        finally:
            await db.close()

        assert mock_prompt.call_count == 2

    async def test_handles_provider_error(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        mock_prompt = AsyncMock(
            side_effect=LLMError("Invalid API key", provider=ProviderType.OPENROUTER),
        )

        with (
            patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)),
            patch("src.scheduler.send_prompt", mock_prompt),
            patch("src.scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            run_id = await execute_monitoring_run(
                project_id="proj-1",
                trigger_type="manual",
            )

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            run = await cursor.fetchone()
            assert run is not None
            assert run["status"] == "failed"
            assert run["completed_queries"] == 0
            assert run["failed_queries"] == 2

            cursor = await db.execute("SELECT * FROM responses WHERE run_id = ?", (run_id,))
            responses = await cursor.fetchall()
            assert len(responses) == 2
            for resp in responses:
                assert resp["error_message"] == "Invalid API key"
        finally:
            await db.close()

    async def test_no_terms_skips_run(self, tmp_path):
        """When no active terms exist, the run should be skipped."""
        db_path = str(tmp_path / "test.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        try:
            await db.executescript(schema_sql)
            now = datetime.now(tz=UTC).isoformat()
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-empty", "Empty Project", 0, now, now),
            )
            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            run_id = await execute_monitoring_run(project_id="proj-empty")

        assert run_id is not None

        db = await aiosqlite.connect(db_path)
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM runs")
            count = await cursor.fetchone()
            assert count is not None
            assert count[0] == 0

            # A configuration_error alert should have been created
            cursor = await db.execute(
                "SELECT alert_type, severity, title FROM alerts WHERE project_id = ?",
                ("proj-empty",),
            )
            alert = await cursor.fetchone()
            assert alert is not None
            assert alert[0] == "configuration_error"
            assert alert[1] == "critical"
        finally:
            await db.close()
