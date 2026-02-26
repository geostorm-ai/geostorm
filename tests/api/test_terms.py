"""Tests for the terms API routes."""

import contextlib
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.routes.terms import router

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
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.executescript(schema_sql)
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test Project", 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_demo_project(db_path: str) -> None:
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO projects (id, name, is_demo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("demo-1", "Demo", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_term(db_path: str, project_id: str = "proj-1") -> None:
    db = await aiosqlite.connect(db_path)
    now = "2024-01-01T00:00:00+00:00"
    try:
        await db.execute(
            "INSERT INTO project_terms"
            " (id, project_id, name, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("term-1", project_id, "best Python framework", 1, now, now),
        )
        await db.commit()
    finally:
        await db.close()


def _patches(db_path: str):
    fake = _fake_db_conn(db_path)
    return (
        patch("src.database.get_db_connection", side_effect=fake),
    )


@pytest.mark.asyncio
async def test_list_terms(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_term(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/terms")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "best Python framework"


@pytest.mark.asyncio
async def test_list_terms_empty(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/proj-1/terms")
            assert resp.status_code == 200
            assert resp.json() == []


@pytest.mark.asyncio
async def test_list_terms_project_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects/nonexistent/terms")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_term(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/terms",
                json={"name": "fastest web framework"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "fastest web framework"
            assert data["project_id"] == "proj-1"
            assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_term_demo_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_demo_project(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/demo-1/terms",
                json={"name": "should fail"},
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_term(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_term(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/projects/proj-1/terms/term-1")
            assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_term_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/projects/proj-1/terms/nonexistent")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_term_demo_403(tmp_path):
    db_path = str(tmp_path / "test.db")
    await _init_db(db_path)
    await _seed_demo_project(db_path)

    (p1,) = _patches(db_path)
    with p1:
        test_app = FastAPI()
        test_app.include_router(router)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/projects/demo-1/terms/term-1")
            assert resp.status_code == 403
