"""FastAPI entry point for GeoStorm."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.database import check_database_health, initialize_database
from src.retention import cleanup_old_responses
from src.routes.alerts import router as alerts_router
from src.routes.projects import router as projects_router
from src.routes.runs import router as runs_router
from src.routes.schedule import router as schedule_router
from src.routes.setup import router as setup_router
from src.routes.terms import router as terms_router
from src.scheduler import scheduling_loop

logger = logging.getLogger(__name__)

_scheduler: AsyncScheduler | None = None

_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    scheduler: str


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle for GeoStorm."""
    global _scheduler  # noqa: PLW0603

    await initialize_database()

    _scheduler = AsyncScheduler()
    async with _scheduler:
        await _scheduler.add_schedule(
            scheduling_loop,
            IntervalTrigger(seconds=60),
            id="monitoring",
        )
        await _scheduler.add_schedule(
            cleanup_old_responses,
            IntervalTrigger(hours=24),
            id="retention_cleanup",
        )
        await _scheduler.start_in_background()
        logger.info("GeoStorm started on port 8080")

        yield

    _scheduler = None
    logger.info("GeoStorm shutting down")


app = FastAPI(
    title="GeoStorm",
    description="Observability for AI-driven software discovery",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(terms_router)
app.include_router(schedule_router)
app.include_router(alerts_router)
app.include_router(runs_router)
app.include_router(setup_router)


@app.get("/health")
async def health_check() -> HealthResponse:
    """Return service health status with a real database ping."""
    db_ok = await check_database_health()
    scheduler_status = "running" if _scheduler is not None else "stopped"
    return HealthResponse(
        status="ok" if db_ok and _scheduler is not None else "degraded",
        database="connected" if db_ok else "unreachable",
        scheduler=scheduler_status,
    )


# Static assets MUST be registered after all API routes.
_ASTRO_ASSETS = _STATIC_DIR / "_astro"
if _ASTRO_ASSETS.is_dir():
    app.mount("/_astro", StaticFiles(directory=str(_ASTRO_ASSETS)), name="astro_assets")
if (_STATIC_DIR / "favicon.svg").is_file():
    @app.get("/favicon.svg", response_model=None)
    async def favicon_svg() -> FileResponse:
        """Serve favicon."""
        return FileResponse(str(_STATIC_DIR / "favicon.svg"))

    @app.get("/favicon.ico", response_model=None)
    async def favicon_ico() -> FileResponse:
        """Serve favicon."""
        return FileResponse(str(_STATIC_DIR / "favicon.ico"))


@app.get("/{_full_path:path}", response_model=None)
async def serve_spa(_full_path: str) -> FileResponse | JSONResponse:
    """Serve static Astro pages.

    This catch-all is intentionally registered last so it never
    shadows /health, /api/*, or /static/* routes.
    """
    if _full_path.startswith("api"):
        return JSONResponse(
            content={"detail": "Not found"},
            status_code=404,
        )

    import re  # noqa: PLC0415

    # /projects/<uuid> → serve the detail page
    if re.match(r"^projects/[^/]+$", _full_path) and _full_path != "projects":
        detail_file = _STATIC_DIR / "projects" / "detail" / "index.html"
        if detail_file.is_file():
            return FileResponse(str(detail_file))

    # Try exact path (e.g. /settings → /settings/index.html)
    page_file = _STATIC_DIR / _full_path / "index.html"
    if page_file.is_file():
        return FileResponse(str(page_file))

    # Try root index as fallback
    index_file = _STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))

    return JSONResponse(
        content={"detail": "Frontend not built. Run pnpm build in web/."},
        status_code=404,
    )
