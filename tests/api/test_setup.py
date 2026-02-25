"""Tests for the setup and settings API routes."""

import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.llm.base import LLMProviderError, PromptResponse, ProviderError, ProviderType
from src.routes.setup import router

_MIGRATIONS = (
    Path(__file__).resolve().parent.parent.parent / "migrations" / "001_initial_schema.sql"
)


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
    try:
        await db.executescript(schema_sql)
        await db.commit()
    finally:
        await db.close()


def _patches(db_path: str):
    fake = _fake_db_conn(db_path)
    return (
        patch("src.routes.setup.get_db_connection", side_effect=fake),
    )


def _fake_settings(api_key: str = ""):
    """Return a mock settings object."""

    class _Settings:
        openrouter_api_key: str = api_key

    return _Settings()


@pytest.mark.asyncio
async def test_setup_status_no_key_no_projects(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_api_key"] is False
            assert data["has_projects"] is False
            assert data["project_count"] == 0


@pytest.mark.asyncio
async def test_setup_status_with_env_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch(
        "src.routes.setup.get_settings",
        return_value=_fake_settings("sk-or-test"),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert resp.status_code == 200
            assert resp.json()["has_api_key"] is True


@pytest.mark.asyncio
async def test_setup_status_with_db_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            "INSERT INTO settings (key, value, updated_at)"
            " VALUES ('openrouter_api_key', 'sk-or-db', '2024-01-01')",
        )
        await db.commit()
    finally:
        await db.close()

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert resp.status_code == 200
            assert resp.json()["has_api_key"] is True


@pytest.mark.asyncio
async def test_setup_status_with_projects(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    now = "2024-01-01T00:00:00+00:00"

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "My Project", 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_projects"] is True
            assert data["project_count"] == 1


@pytest.mark.asyncio
async def test_setup_status_demo_projects_not_counted(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    now = "2024-01-01T00:00:00+00:00"

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("demo-1", "Demo", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_projects"] is False
            assert data["project_count"] == 0


@pytest.mark.asyncio
async def test_api_key_status_not_configured(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/settings/api-key-status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["configured"] is False
            assert data["source"] is None


@pytest.mark.asyncio
async def test_api_key_status_from_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch(
        "src.routes.setup.get_settings",
        return_value=_fake_settings("sk-or-env"),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/settings/api-key-status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["configured"] is True
            assert data["source"] == "environment"


@pytest.mark.asyncio
async def test_store_and_retrieve_api_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/settings/api-key",
                json={"key": "sk-or-new-key"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "stored"

            resp2 = await client.get("/api/settings/api-key-status")
            assert resp2.status_code == 200
            assert resp2.json()["configured"] is True
            assert resp2.json()["source"] == "database"


@pytest.mark.asyncio
async def test_delete_api_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1, patch("src.routes.setup.get_settings", return_value=_fake_settings()):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/settings/api-key",
                json={"key": "sk-or-to-delete"},
            )

            resp = await client.delete("/api/settings/api-key")
            assert resp.status_code == 204

            resp2 = await client.get("/api/settings/api-key-status")
            assert resp2.json()["configured"] is False


# ---------------------------------------------------------------------------
# Autofill endpoint tests
# ---------------------------------------------------------------------------

_AUTOFILL_LLM_JSON = (
    '{"brand_name":"Supabase","brand_aliases":["supabase"],'
    '"description":"Open source Firebase alternative.",'
    '"competitors":["Firebase","PlanetScale","Neon"],'
    '"monitoring_terms":["Firebase alternative","open source BaaS",'
    '"Supabase vs Firebase","backend for React app","serverless database platform"]}'
)


def _fake_llm_response(text: str = _AUTOFILL_LLM_JSON) -> PromptResponse:
    return PromptResponse(
        text=text,
        model_id="google/gemini-2.0-flash-001",
        provider=ProviderType.OPENROUTER,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
        cost_usd=0.001,
    )


@pytest.mark.asyncio
async def test_autofill_success(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    mock_provider = AsyncMock()
    mock_provider.send_prompt.return_value = _fake_llm_response()
    mock_provider.close = AsyncMock()

    (p1,) = _patches(db_path)
    with (
        p1,
        patch("src.routes.setup.get_settings", return_value=_fake_settings("sk-or-test")),
        patch("src.routes.setup.get_api_key", return_value="sk-or-test"),
        patch("src.routes.setup.OpenRouterProvider", return_value=mock_provider),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/setup/autofill", json={"input": "Supabase"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["brand_name"] == "Supabase"
            assert "Firebase alternative" in data["monitoring_terms"]
            assert len(data["competitors"]) == 3


@pytest.mark.asyncio
async def test_autofill_no_api_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with (
        p1,
        patch("src.routes.setup.get_settings", return_value=_fake_settings()),
        patch("src.routes.setup.get_api_key", return_value=None),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/setup/autofill", json={"input": "Supabase"})
            assert resp.status_code == 400


@pytest.mark.asyncio
async def test_autofill_invalid_json_from_llm(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    mock_provider = AsyncMock()
    mock_provider.send_prompt.return_value = _fake_llm_response(text="not valid json")
    mock_provider.close = AsyncMock()

    (p1,) = _patches(db_path)
    with (
        p1,
        patch("src.routes.setup.get_settings", return_value=_fake_settings("sk-or-test")),
        patch("src.routes.setup.get_api_key", return_value="sk-or-test"),
        patch("src.routes.setup.OpenRouterProvider", return_value=mock_provider),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/setup/autofill", json={"input": "Supabase"})
            assert resp.status_code == 502


@pytest.mark.asyncio
async def test_autofill_llm_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    mock_provider = AsyncMock()
    mock_provider.send_prompt.side_effect = LLMProviderError(
        ProviderError(
            code="http_500",
            message="Internal error",
            provider=ProviderType.OPENROUTER,
            is_retryable=False,
        ),
    )
    mock_provider.close = AsyncMock()

    (p1,) = _patches(db_path)
    with (
        p1,
        patch("src.routes.setup.get_settings", return_value=_fake_settings("sk-or-test")),
        patch("src.routes.setup.get_api_key", return_value="sk-or-test"),
        patch("src.routes.setup.OpenRouterProvider", return_value=mock_provider),
    ):
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/setup/autofill", json={"input": "Supabase"})
            assert resp.status_code == 502
