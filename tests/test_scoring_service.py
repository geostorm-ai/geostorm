"""Tests for the perception scoring service."""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from src.container import scoring_service
from src.models import MentionType, TrendDirection
from src.services.scoring_service import ScoreResult, calculate_overall_score, calculate_trend

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


async def _setup_test_db(db_path: str) -> None:
    """Initialize a test database with schema and seed data for scoring tests."""
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
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "proj-1", "completed", "manual", 4, now, now),
        )

        # 4 responses: resp-1..4, some with errors
        for i in range(1, 5):
            error = "timeout" if i == 4 else None
            await db.execute(
                "INSERT INTO responses"
                " (id, run_id, project_id, term_id, provider_name, model_name,"
                "  response_text, error_message, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"resp-{i}", "run-1", "proj-1", "term-1", "openai", "gpt-4o", f"Response {i}", error, now),
            )

        # Brand mentions on resp-1 and resp-2
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name,"
            " list_position, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("m-1", "resp-1", MentionType.BRAND.value, "MyBrand", 1, now),
        )
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name,"
            " list_position, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("m-2", "resp-2", MentionType.BRAND.value, "MyBrand", 3, now),
        )

        # Competitor mentions on resp-1 and resp-3
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name,"
            " list_position, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("m-3", "resp-1", MentionType.COMPETITOR.value, "CompA", 2, now),
        )
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name,"
            " list_position, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("m-4", "resp-3", MentionType.COMPETITOR.value, "CompA", 1, now),
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


# ---------------------------------------------------------------------------
# calculate_trend tests
# ---------------------------------------------------------------------------


class TestCalculateTrend:
    def test_up(self):
        result = calculate_trend(0.8, 0.5)
        assert result == TrendDirection.UP

    def test_down(self):
        result = calculate_trend(0.3, 0.7)
        assert result == TrendDirection.DOWN

    def test_stable(self):
        result = calculate_trend(0.5, 0.48)
        assert result == TrendDirection.STABLE

    def test_no_previous(self):
        result = calculate_trend(0.5, None)
        assert result == TrendDirection.STABLE


# ---------------------------------------------------------------------------
# calculate_overall_score tests
# ---------------------------------------------------------------------------


class TestCalculateOverallScore:
    def test_perfect(self):
        score = calculate_overall_score(1.0, 1.0, 1.0)
        # share=50, position=90% of 30=27, delta=100% of 20=20 => 97
        assert score > 90.0
        assert score <= 100.0

    def test_zero(self):
        score = calculate_overall_score(0.0, None, None)
        # share=0, position=neutral 50->15, delta=neutral 50->10 => 25
        assert score < 30.0
        assert score >= 0.0

    def test_partial(self):
        score = calculate_overall_score(0.5, 3.0, 0.1)
        # share=25, position=(10-3)/10*100=70->21, delta=(0.1+1)/2*100=55->11 => ~57
        assert 40.0 < score < 70.0


# ---------------------------------------------------------------------------
# calculate_run_scores tests
# ---------------------------------------------------------------------------


class TestCalculateRunScores:
    async def test_partial_share(self, tmp_path):
        """2 of 3 non-error responses have brand mentions -> share ~0.67."""
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-1", "proj-1")

        # Should have per-group score + aggregate
        assert len(scores) >= 1
        # Find the (term-1, openai) group — 3 non-error responses, 2 brand mentions
        group_score = next(s for s in scores if s.term_id == "term-1" and s.provider_name == "openai")
        assert abs(group_score.recommendation_share - 2 / 3) < 0.01

    async def test_perfect_share(self, tmp_path):
        """All responses mention the brand -> share=1.0."""
        db_path = str(tmp_path / "test_perfect.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-1", "Test", 0, now, now),
            )
            await db.execute(
                "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("run-p", "proj-1", "completed", "manual", now),
            )
            for i in range(1, 4):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rp-{i}", "run-p", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"mp-{i}", f"rp-{i}", MentionType.BRAND.value, "MyBrand", now),
                )
            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-p", "proj-1")

        group = next(s for s in scores if s.term_id == "t1")
        assert group.recommendation_share == 1.0

    async def test_zero_share(self, tmp_path):
        """No brand mentions -> share=0.0."""
        db_path = str(tmp_path / "test_zero.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-1", "Test", 0, now, now),
            )
            await db.execute(
                "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("run-z", "proj-1", "completed", "manual", now),
            )
            for i in range(1, 4):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rz-{i}", "run-z", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-z", "proj-1")

        group = next(s for s in scores if s.term_id == "t1")
        assert group.recommendation_share == 0.0

    async def test_position_average(self, tmp_path):
        """Brand at positions 1, 3, 5 -> avg=3.0."""
        db_path = str(tmp_path / "test_pos.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-1", "Test", 0, now, now),
            )
            await db.execute(
                "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("run-pos", "proj-1", "completed", "manual", now),
            )
            for i, pos in enumerate([1, 3, 5], start=1):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rpos-{i}", "run-pos", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name,"
                    " list_position, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"mpos-{i}", f"rpos-{i}", MentionType.BRAND.value, "MyBrand", pos, now),
                )
            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-pos", "proj-1")

        group = next(s for s in scores if s.term_id == "t1")
        assert group.position_avg == 3.0

    async def test_competitor_delta(self, tmp_path):
        """Brand share 0.8, top competitor share 0.6 -> delta=0.2."""
        db_path = str(tmp_path / "test_delta.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-1", "Test", 0, now, now),
            )
            await db.execute(
                "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("run-d", "proj-1", "completed", "manual", now),
            )
            # 5 responses: brand mentioned in 4 (0.8), competitor in 3 (0.6)
            for i in range(1, 6):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rd-{i}", "run-d", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
            # Brand mentions on 4 of 5
            for i in range(1, 5):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"md-b{i}", f"rd-{i}", MentionType.BRAND.value, "MyBrand", now),
                )
            # Competitor mentions on 3 of 5
            for i in range(1, 4):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"md-c{i}", f"rd-{i}", MentionType.COMPETITOR.value, "CompA", now),
                )
            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-d", "proj-1")

        group = next(s for s in scores if s.term_id == "t1")
        assert group.recommendation_share == 0.8
        assert group.competitor_delta is not None
        assert abs(group.competitor_delta - 0.2) < 0.01

    async def test_error_responses_excluded(self, tmp_path):
        """Responses with error_message are not counted."""
        db_path = str(tmp_path / "test_err.db")
        await _setup_test_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            scores = await scoring_service.calculate_run_scores("run-1", "proj-1")

        # resp-4 has error so only 3 responses counted
        group = next(s for s in scores if s.term_id == "term-1")
        # 2 brand mentions out of 3 non-error responses
        assert abs(group.recommendation_share - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# store_scores tests
# ---------------------------------------------------------------------------


class TestStoreScores:
    async def test_persists_scores(self, tmp_path):
        db_path = str(tmp_path / "test_store.db")
        schema_sql = _MIGRATIONS.read_text()
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj-1", "Test", 0, now, now),
            )
            await db.commit()
        finally:
            await db.close()

        results = [
            ScoreResult(
                term_id="t1",
                provider_name="openai",
                recommendation_share=0.75,
                position_avg=2.5,
                competitor_delta=0.1,
                overall_score=65.0,
                trend_direction=TrendDirection.UP,
            ),
            ScoreResult(
                term_id=None,
                provider_name=None,
                recommendation_share=0.6,
                position_avg=None,
                competitor_delta=None,
                overall_score=55.0,
                trend_direction=TrendDirection.STABLE,
            ),
        ]

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await scoring_service.store_scores("proj-1", results)

        assert len(ids) == 2

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM perception_scores ORDER BY recommendation_share DESC")
            rows = await cursor.fetchall()
            assert len(rows) == 2
            assert rows[0]["recommendation_share"] == 0.75
            assert rows[0]["term_id"] == "t1"
            assert rows[0]["trend_direction"] == "up"
            assert rows[1]["term_id"] is None
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# calculate_and_store_scores integration test
# ---------------------------------------------------------------------------


class TestCalculateAndStoreScores:
    async def test_pipeline(self, tmp_path):
        db_path = str(tmp_path / "test_pipeline.db")
        await _setup_test_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await scoring_service.calculate_and_store_scores("run-1", "proj-1")

        assert len(ids) >= 2  # at least one group + aggregate

        db = await aiosqlite.connect(db_path)
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM perception_scores")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == len(ids)
        finally:
            await db.close()
