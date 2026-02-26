"""Tests for the mention detection and storage service."""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from src.container import mention_service
from src.models import MentionType
from src.services.mention_service import DetectedMention, detect_mentions, parse_numbered_list

_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


async def _setup_test_db(db_path: str) -> None:
    """Initialize a test database with schema and seed data for mention tests."""
    schema_sql = _MIGRATIONS.read_text()
    db = await aiosqlite.connect(db_path)
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(schema_sql)

        now = datetime.now(tz=UTC).isoformat()

        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test", 0, now, now),
        )
        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, total_queries, started_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "proj-1", "completed", "manual", 1, now, now),
        )
        await db.execute(
            "INSERT INTO responses"
            " (id, run_id, project_id, term_id, provider_name, model_name, response_text, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("resp-1", "run-1", "proj-1", "term-1", "openrouter", "gpt-4o", "test", now),
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
# parse_numbered_list tests
# ---------------------------------------------------------------------------


class TestParseNumberedList:
    def test_standard_list(self):
        text = "1. Litestar\n2. Flask\n3. FastAPI"
        items = parse_numbered_list(text)
        assert len(items) == 3
        assert items[0].position == 1
        assert items[0].text == "Litestar"
        assert items[1].position == 2
        assert items[1].text == "Flask"
        assert items[2].position == 3
        assert items[2].text == "FastAPI"

    def test_parenthesis_format(self):
        text = "1) Litestar\n2) Flask"
        items = parse_numbered_list(text)
        assert len(items) == 2
        assert items[0].position == 1
        assert items[0].text == "Litestar"
        assert items[1].position == 2
        assert items[1].text == "Flask"

    def test_markdown_bold(self):
        text = "**1. Litestar**\n**2. Flask**"
        items = parse_numbered_list(text)
        assert len(items) == 2
        assert items[0].position == 1
        # Text may include trailing **, that's fine as long as it's parsed
        assert "Litestar" in items[0].text
        assert items[1].position == 2
        assert "Flask" in items[1].text

    def test_no_list(self):
        text = "Litestar is a great web framework for building applications quickly."
        items = parse_numbered_list(text)
        assert items == []

    def test_large_list(self):
        lines = [f"{i}. Item{i}" for i in range(1, 22)]
        text = "\n".join(lines)
        items = parse_numbered_list(text)
        assert len(items) == 21
        assert items[0].position == 1
        assert items[20].position == 21
        assert items[20].text == "Item21"


# ---------------------------------------------------------------------------
# detect_mentions tests
# ---------------------------------------------------------------------------


class TestDetectMentions:
    def test_exact_match(self):
        text = "I recommend FastAPI for building modern APIs."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.BRAND
        assert mentions[0].target_name == "FastAPI"

    def test_case_insensitive(self):
        text = "You should use fastapi for your next project."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.BRAND
        assert mentions[0].target_name == "FastAPI"

    def test_alias_match(self):
        text = "Consider using FastAPI Python for your web service."
        mentions = detect_mentions(
            text,
            brand_name="FastAPI",
            brand_aliases=["FastAPI Python"],
            competitors=[],
        )
        # Should find both the alias "FastAPI Python" and the base "FastAPI"
        target_names = {m.target_name for m in mentions}
        assert "FastAPI Python" in target_names

    def test_word_boundaries(self):
        text = "Try FastAPIExtra for extended features."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 0

    def test_competitor_detection(self):
        text = "Litestar and Flask are popular alternatives."
        mentions = detect_mentions(
            text,
            brand_name="FastAPI",
            brand_aliases=[],
            competitors=["Litestar", "Flask"],
        )
        competitor_mentions = [m for m in mentions if m.mention_type == MentionType.COMPETITOR]
        assert len(competitor_mentions) == 2
        names = {m.target_name for m in competitor_mentions}
        assert names == {"Litestar", "Flask"}

    def test_multiple_mentions(self):
        text = "FastAPI is fast. FastAPI is also easy to use. FastAPI has great docs."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 3
        for m in mentions:
            assert m.mention_type == MentionType.BRAND
            assert m.target_name == "FastAPI"

    def test_context_extraction(self):
        text = "For building REST APIs, I strongly recommend FastAPI because it is very performant and modern."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 1
        mention = mentions[0]
        # context_before should end right before "FastAPI"
        assert len(mention.context_before) <= 50
        assert mention.context_before.endswith("recommend ")
        # context_after should start right after "FastAPI"
        assert len(mention.context_after) <= 50
        assert mention.context_after.startswith(" because")

    def test_list_position_tracking(self):
        text = "1. Litestar\n2. Flask\n3. FastAPI\n4. Tornado"
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 1
        assert mentions[0].list_position == 3

    def test_empty_response(self):
        mentions = detect_mentions("", brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert mentions == []

    def test_markdown_formatted_names(self):
        text = "I recommend **FastAPI** for modern web development."
        mentions = detect_mentions(text, brand_name="FastAPI", brand_aliases=[], competitors=[])
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.BRAND


# ---------------------------------------------------------------------------
# store_mentions tests
# ---------------------------------------------------------------------------


class TestStoreMentions:
    async def test_db_persistence(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        detected = [
            DetectedMention(
                mention_type=MentionType.BRAND,
                target_name="FastAPI",
                position_chars=10,
                position_words=2,
                list_position=1,
                context_before="recommend ",
                context_after=" for APIs",
            ),
            DetectedMention(
                mention_type=MentionType.COMPETITOR,
                target_name="Litestar",
                position_chars=50,
                position_words=8,
                list_position=None,
                context_before="also try ",
                context_after=" as well",
            ),
        ]

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await mention_service.store_mentions("resp-1", detected)

        assert len(ids) == 2

        # Verify data persisted
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM mentions WHERE response_id = ?", ("resp-1",))
            rows = await cursor.fetchall()
            assert len(rows) == 2

            row_by_name = {row["target_name"]: row for row in rows}
            assert row_by_name["FastAPI"]["mention_type"] == "brand"
            assert row_by_name["FastAPI"]["position_chars"] == 10
            assert row_by_name["FastAPI"]["list_position"] == 1
            assert row_by_name["Litestar"]["mention_type"] == "competitor"
            assert row_by_name["Litestar"]["list_position"] is None
        finally:
            await db.close()

    async def test_empty_list_noop(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await mention_service.store_mentions("resp-1", [])

        assert ids == []

        # Verify no rows written
        db = await aiosqlite.connect(db_path)
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM mentions")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 0
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# detect_and_store_mentions_for_response tests
# ---------------------------------------------------------------------------


class TestDetectAndStoreMentionsForResponse:
    async def test_end_to_end(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await _setup_test_db(db_path)

        response_text = "1. Litestar\n2. Flask\n3. FastAPI"

        with patch("src.database.get_db_connection", side_effect=_fake_db_conn(db_path)):
            ids = await mention_service.detect_and_store_mentions_for_response(
                response_id="resp-1",
                response_text=response_text,
                brand_name="FastAPI",
                brand_aliases=[],
                competitors=["Litestar", "Flask"],
            )

        assert len(ids) >= 3  # at least brand + 2 competitors

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM mentions WHERE response_id = ?", ("resp-1",))
            rows = await cursor.fetchall()
            assert len(rows) == len(ids)

            types = {row["mention_type"] for row in rows}
            assert "brand" in types
            assert "competitor" in types
        finally:
            await db.close()
