"""Tests for the change detection and alerting service."""

import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from src.container import change_detection_service
from src.models import AlertSeverity, AlertType, MentionType
from src.services.change_detection import Baseline, DetectedChange

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


async def _setup_baseline_db(db_path: str) -> None:
    """Initialize DB with schema, project, a run with responses and mentions for baseline."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(schema_sql)

        now = datetime.now(tz=UTC).isoformat()
        yesterday = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()

        # Project
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )

        # Historical run (for baseline)
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("run-old", "proj-1", "completed", "manual", yesterday),
        )

        # Current run
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("run-new", "proj-1", "completed", "manual", now),
        )

        # Historical perception score
        await db.execute(
            "INSERT INTO perception_scores"
            " (id, project_id, recommendation_share, position_avg, overall_score,"
            "  period_start, period_end, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ps-1", "proj-1", 0.9, 2.0, 85.0, yesterday, yesterday, yesterday),
        )

        # Historical responses + mentions (for known competitors)
        await db.execute(
            "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
            " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("resp-old-1", "run-old", "proj-1", "t1", "openai", "gpt-4o", "text", yesterday),
        )
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("m-old-1", "resp-old-1", MentionType.COMPETITOR.value, "ExistingComp", yesterday),
        )
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name, list_position, detected_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("m-old-2", "resp-old-1", MentionType.BRAND.value, "MyBrand", 1, yesterday),
        )

        await db.commit()
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# detect_competitor_emergence tests
# ---------------------------------------------------------------------------


class TestDetectCompetitorEmergence:
    async def test_new_competitor_triggers_alert(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        # Add a new competitor mention to the current run
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.execute(
                "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("resp-new-1", "run-new", "proj-1", "t1", "openai", "gpt-4o", "text", now),
            )
            await db.execute(
                "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("m-new-1", "resp-new-1", MentionType.COMPETITOR.value, "NewTool", now),
            )
            await db.commit()
        finally:
            await db.close()

        baseline = Baseline(
            avg_recommendation_share=0.9,
            avg_position=2.0,
            known_competitors={"ExistingComp"},
            provider_shares={"openai": 0.9},
        )

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_competitor_emergence("proj-1", "run-new", baseline)

        assert len(changes) == 1
        assert changes[0].alert_type == AlertType.COMPETITOR_EMERGENCE
        assert changes[0].severity == AlertSeverity.CRITICAL
        assert "NewTool" in changes[0].title

    async def test_existing_competitor_no_alert(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        # Add existing competitor mention to the current run
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            await db.execute(
                "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("resp-new-1", "run-new", "proj-1", "t1", "openai", "gpt-4o", "text", now),
            )
            await db.execute(
                "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("m-new-1", "resp-new-1", MentionType.COMPETITOR.value, "ExistingComp", now),
            )
            await db.commit()
        finally:
            await db.close()

        baseline = Baseline(
            avg_recommendation_share=0.9,
            avg_position=2.0,
            known_competitors={"ExistingComp"},
            provider_shares={"openai": 0.9},
        )

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_competitor_emergence("proj-1", "run-new", baseline)

        assert changes == []


# ---------------------------------------------------------------------------
# detect_disappearance tests
# ---------------------------------------------------------------------------


class TestDetectDisappearance:
    async def test_brand_disappears_triggers_critical(self, tmp_path):
        """Baseline share=0.9, current=0.1 -> CRITICAL alert."""
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        # Current run: 10 responses, only 1 has a brand mention
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            for i in range(1, 11):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"resp-dis-{i}", "run-new", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
            # Only 1 brand mention
            await db.execute(
                "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("m-dis-1", "resp-dis-1", MentionType.BRAND.value, "MyBrand", now),
            )
            await db.commit()
        finally:
            await db.close()

        baseline = Baseline(
            avg_recommendation_share=0.9,
            avg_position=2.0,
            known_competitors={"ExistingComp"},
            provider_shares={"openai": 0.9},
        )

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_disappearance("proj-1", "run-new", baseline)

        assert len(changes) == 1
        assert changes[0].alert_type == AlertType.DISAPPEARANCE
        assert changes[0].severity == AlertSeverity.CRITICAL

    async def test_brand_still_present_no_alert(self, tmp_path):
        """Baseline share=0.9, current=0.8 -> no alert."""
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        # Current run: 10 responses, 8 have brand mentions
        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            for i in range(1, 11):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"resp-pres-{i}", "run-new", "proj-1", "t1", "openai", "gpt-4o", "text", now),
                )
            for i in range(1, 9):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"m-pres-{i}", f"resp-pres-{i}", MentionType.BRAND.value, "MyBrand", now),
                )
            await db.commit()
        finally:
            await db.close()

        baseline = Baseline(
            avg_recommendation_share=0.9,
            avg_position=2.0,
            known_competitors={"ExistingComp"},
            provider_shares={"openai": 0.9},
        )

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_disappearance("proj-1", "run-new", baseline)

        assert changes == []


# ---------------------------------------------------------------------------
# detect_share_drop tests
# ---------------------------------------------------------------------------


class TestDetectShareDrop:
    async def test_major_drop_triggers_warning(self, tmp_path):
        """Baseline=0.8, current=0.6 (20pp drop) -> WARNING."""
        baseline = Baseline(
            avg_recommendation_share=0.8,
            avg_position=2.0,
            known_competitors=set(),
            provider_shares={},
        )

        changes = await change_detection_service.detect_share_drop("proj-1", "run-1", baseline, current_share=0.6)

        assert len(changes) == 1
        assert changes[0].alert_type == AlertType.RECOMMENDATION_SHARE_DROP
        assert changes[0].severity == AlertSeverity.WARNING

    async def test_minor_drop_no_alert(self, tmp_path):
        """Baseline=0.8, current=0.75 (5pp drop) -> no alert."""
        baseline = Baseline(
            avg_recommendation_share=0.8,
            avg_position=2.0,
            known_competitors=set(),
            provider_shares={},
        )

        changes = await change_detection_service.detect_share_drop("proj-1", "run-1", baseline, current_share=0.75)

        assert changes == []


# ---------------------------------------------------------------------------
# detect_position_degradation tests
# ---------------------------------------------------------------------------


class TestDetectPositionDegradation:
    async def test_worsens_triggers_warning(self, tmp_path):
        """Baseline pos=2.0, current=4.5 -> WARNING (2.5 places worse)."""
        baseline = Baseline(
            avg_recommendation_share=0.8,
            avg_position=2.0,
            known_competitors=set(),
            provider_shares={},
        )

        changes = await change_detection_service.detect_position_degradation(
            "proj-1", "run-1", baseline, current_position=4.5,
        )

        assert len(changes) == 1
        assert changes[0].alert_type == AlertType.POSITION_DEGRADATION
        assert changes[0].severity == AlertSeverity.WARNING

    async def test_improves_no_alert(self, tmp_path):
        """Baseline pos=4.0, current=2.0 -> no alert (improvement)."""
        baseline = Baseline(
            avg_recommendation_share=0.8,
            avg_position=4.0,
            known_competitors=set(),
            provider_shares={},
        )

        changes = await change_detection_service.detect_position_degradation(
            "proj-1", "run-1", baseline, current_position=2.0,
        )

        assert changes == []


# ---------------------------------------------------------------------------
# detect_model_divergence tests
# ---------------------------------------------------------------------------


class TestDetectModelDivergence:
    async def test_high_variance_triggers_warning(self, tmp_path):
        """Provider A: 80%, Provider B: 40% -> WARNING (40pp spread)."""
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            # Provider A: 5 responses, 4 brand mentions (80%)
            for i in range(1, 6):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rdiv-a{i}", "run-new", "proj-1", "t1", "provider_a", "model-a", "text", now),
                )
            for i in range(1, 5):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"mdiv-a{i}", f"rdiv-a{i}", MentionType.BRAND.value, "MyBrand", now),
                )

            # Provider B: 5 responses, 2 brand mentions (40%)
            for i in range(1, 6):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rdiv-b{i}", "run-new", "proj-1", "t1", "provider_b", "model-b", "text", now),
                )
            for i in range(1, 3):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"mdiv-b{i}", f"rdiv-b{i}", MentionType.BRAND.value, "MyBrand", now),
                )

            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_model_divergence("proj-1", "run-new")

        assert len(changes) == 1
        assert changes[0].alert_type == AlertType.MODEL_DIVERGENCE
        assert changes[0].severity == AlertSeverity.WARNING

    async def test_low_variance_no_alert(self, tmp_path):
        """Provider A: 60%, Provider B: 55% -> no alert (5pp spread)."""
        db_path = str(tmp_path / "test.db")
        await _setup_baseline_db(db_path)

        db = await aiosqlite.connect(db_path)
        now = datetime.now(tz=UTC).isoformat()
        try:
            # Provider A: 20 responses, 12 brand mentions (60%)
            for i in range(1, 21):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rlow-a{i}", "run-new", "proj-1", "t1", "provider_a", "model-a", "text", now),
                )
            for i in range(1, 13):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"mlow-a{i}", f"rlow-a{i}", MentionType.BRAND.value, "MyBrand", now),
                )

            # Provider B: 20 responses, 11 brand mentions (55%)
            for i in range(1, 21):
                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, provider_name,"
                    " model_name, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"rlow-b{i}", "run-new", "proj-1", "t1", "provider_b", "model-b", "text", now),
                )
            for i in range(1, 12):
                await db.execute(
                    "INSERT INTO mentions (id, response_id, mention_type, target_name, detected_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (f"mlow-b{i}", f"rlow-b{i}", MentionType.BRAND.value, "MyBrand", now),
                )

            await db.commit()
        finally:
            await db.close()

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            changes = await change_detection_service.detect_model_divergence("proj-1", "run-new")

        assert changes == []


# ---------------------------------------------------------------------------
# store_alerts tests
# ---------------------------------------------------------------------------


class TestStoreAlerts:
    async def test_persists_alerts(self, tmp_path):
        db_path = str(tmp_path / "test.db")
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

        from src.models import AlertMetadata

        changes = [
            DetectedChange(
                alert_type=AlertType.COMPETITOR_EMERGENCE,
                severity=AlertSeverity.CRITICAL,
                title="New competitor detected: NewTool",
                message="NewTool now appears in AI recommendations for your monitored terms",
                metadata=AlertMetadata(competitor_name="NewTool", run_id="run-1"),
            ),
        ]

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await change_detection_service.store_alerts("proj-1", changes)

        assert len(ids) == 1

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM alerts WHERE project_id = ?", ("proj-1",))
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["alert_type"] == "competitor_emergence"
            assert rows[0]["severity"] == "critical"
            assert rows[0]["title"] == "New competitor detected: NewTool"
            assert rows[0]["metadata_json"] is not None
        finally:
            await db.close()

    async def test_empty_changes_noop(self, tmp_path):
        db_path = str(tmp_path / "test.db")
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

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await change_detection_service.store_alerts("proj-1", [])

        assert ids == []
