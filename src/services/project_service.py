"""Service layer for projects, brands, and competitors."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import logfire

from src.schemas import (
    BrandResponse,
    CompetitorResponse,
    ProjectCreatedResponse,
    ProjectDetailResponse,
    ProjectResponse,
)

if TYPE_CHECKING:
    from src.repos.project_repo import ProjectRepo
    from src.repos.provider_repo import ProviderRepo
    from src.repos.run_repo import RunRepo
    from src.repos.schedule_repo import ScheduleRepo
    from src.repos.term_repo import TermRepo


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepo,
        provider_repo: ProviderRepo,
        run_repo: RunRepo,
        schedule_repo: ScheduleRepo,
        term_repo: TermRepo,
    ) -> None:
        self._project_repo = project_repo
        self._provider_repo = provider_repo
        self._run_repo = run_repo
        self._schedule_repo = schedule_repo
        self._term_repo = term_repo

    async def list_projects(self) -> list[ProjectResponse]:
        """Return all active projects with scores, run counts, alerts."""
        rows = await self._project_repo.list_projects()
        return [ProjectResponse(**dict(row)) for row in rows]

    async def create_project(  # noqa: PLR0913
        self,
        name: str,
        description: str | None,
        brand_name: str | None,
        brand_aliases: list[str],
        brand_description: str | None,
        brand_website: str | None,
    ) -> ProjectCreatedResponse:
        """Orchestrate project + brand + schedule + default providers creation."""
        now = datetime.now(tz=UTC).isoformat()
        project_id = uuid.uuid4().hex
        brand_id = uuid.uuid4().hex
        schedule_id = uuid.uuid4().hex

        await self._project_repo.create_project(project_id, name, description, False, now)
        await self._project_repo.create_brand(
            brand_id, project_id, brand_name or name,
            json.dumps(brand_aliases), brand_description, brand_website, now,
        )
        await self._schedule_repo.create_schedule(schedule_id, project_id, 14, "[0,1,2,3,4]", True, now)

        default_providers = [
            ("openrouter", "anthropic/claude-sonnet-4.6"),
            ("openrouter", "openai/gpt-5.2"),
            ("openrouter", "google/gemini-3-flash-preview"),
        ]
        for prov_name, model_name in default_providers:
            await self._provider_repo.create_provider(
                uuid.uuid4().hex, project_id, prov_name, model_name, now,
            )

        # Seed a default monitoring term from the brand/project name so
        # the first "Run Now" click actually executes queries.
        default_term_name = brand_name or name
        await self._term_repo.create_term(
            uuid.uuid4().hex, project_id, default_term_name, None, now,
        )

        return ProjectCreatedResponse(
            id=project_id,
            name=name,
            brand_id=brand_id,
            schedule_id=schedule_id,
            providers_count=len(default_providers),
            created_at=now,
        )

    async def get_project_detail(self, project_id: str, project_row: Any) -> ProjectDetailResponse:  # noqa: ANN401
        """Aggregate project data from repos."""
        run_count = await self._run_repo.count_runs_for_project(project_id)
        brand_row = await self._project_repo.get_brand(project_id)
        brand: dict[str, Any] | None = None
        if brand_row:
            brand = dict(brand_row)
            brand["aliases"] = json.loads(brand["aliases_json"]) if brand["aliases_json"] else []

        competitor_rows = await self._project_repo.list_competitors(project_id)
        competitors = []
        for row in competitor_rows:
            comp = dict(row)
            comp["aliases"] = json.loads(comp["aliases_json"]) if comp["aliases_json"] else []
            competitors.append(comp)

        term_rows = await self._term_repo.list_terms(project_id)
        terms = [dict(row) for row in term_rows]

        schedule_row = await self._schedule_repo.get_schedule(project_id)
        schedule: dict[str, Any] | None = None
        if schedule_row:
            schedule = dict(schedule_row)
            schedule["days_of_week"] = json.loads(schedule["days_of_week_json"])

        return ProjectDetailResponse(
            **dict(project_row),
            run_count=run_count,
            brand=brand,
            competitors=competitors,
            terms=terms,
            schedule=schedule,
        )

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> ProjectResponse | None:
        """Update a project. Returns shaped response or None."""
        row = await self._project_repo.update_project(project_id, updates)
        if not row:
            return None
        return ProjectResponse(**dict(row))

    async def soft_delete_project(self, project_id: str) -> None:
        """Soft-delete a project."""
        now = datetime.now(tz=UTC).isoformat()
        await self._project_repo.soft_delete_project(project_id, now)

    async def get_brand(self, project_id: str) -> BrandResponse | None:
        """Return brand details for a project."""
        row = await self._project_repo.get_brand(project_id)
        if not row:
            return None
        return BrandResponse(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
            description=row["description"],
            website=row["website"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def update_brand(self, project_id: str, updates: dict[str, Any]) -> BrandResponse | None:
        """Update a brand. Returns shaped response or None."""
        row = await self._project_repo.update_brand(project_id, updates)
        if not row:
            return None
        return BrandResponse(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
            description=row["description"],
            website=row["website"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_competitors(self, project_id: str) -> list[CompetitorResponse]:
        """Return competitors for a project."""
        rows = await self._project_repo.list_competitors(project_id)
        return [
            CompetitorResponse(
                id=row["id"],
                project_id=row["project_id"],
                name=row["name"],
                aliases=json.loads(row["aliases_json"]) if row["aliases_json"] else [],
                website=row["website"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def create_competitor(
        self, project_id: str, name: str, aliases: list[str], website: str | None,
    ) -> CompetitorResponse:
        """Create a competitor."""
        now = datetime.now(tz=UTC).isoformat()
        competitor_id = uuid.uuid4().hex
        await self._project_repo.create_competitor(
            competitor_id, project_id, name, json.dumps(aliases), website, now,
        )
        return CompetitorResponse(
            id=competitor_id,
            project_id=project_id,
            name=name,
            aliases=aliases,
            website=website,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    async def delete_competitor(self, competitor_id: str, project_id: str) -> int:
        """Delete a competitor. Returns rowcount."""
        return await self._project_repo.delete_competitor(competitor_id, project_id)


_background_tasks: set[asyncio.Task[Any]] = set()


async def clear_and_trigger_monitoring(project_id: str) -> dict[str, str]:
    """Clear run data and launch a background monitoring task."""
    from src.container import run_repo, term_repo  # noqa: PLC0415
    from src.llm.factory import get_available_providers  # noqa: PLC0415
    from src.scheduler import execute_monitoring_run  # noqa: PLC0415

    available = await get_available_providers()
    if not available:
        return {"error": "no_api_key"}

    terms = await term_repo.list_active_term_ids_and_names(project_id)
    if not terms:
        return {"error": "no_terms"}

    for t in list(_background_tasks):
        if not t.done():
            t.cancel()
    _background_tasks.clear()

    await run_repo.delete_project_run_data(project_id)

    logfire.info("monitoring triggered", project_id=project_id, trigger="manual")
    task = asyncio.create_task(execute_monitoring_run(project_id, trigger_type="manual"))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"status": "accepted", "message": "Monitoring run triggered"}
