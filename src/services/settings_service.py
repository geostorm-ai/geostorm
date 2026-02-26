"""Service layer for application settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import get_settings
from src.schemas import ApiKeyStatusResponse, SetupStatusResponse

if TYPE_CHECKING:
    from src.repos.project_repo import ProjectRepo
    from src.repos.settings_repo import SettingsRepo


class SettingsService:
    def __init__(self, settings_repo: SettingsRepo, project_repo: ProjectRepo) -> None:
        self._settings_repo = settings_repo
        self._project_repo = project_repo

    async def get_setup_status(self) -> SetupStatusResponse:
        """Check API key and project status."""
        has_api_key = False

        value = await self._settings_repo.get_setting("openrouter_api_key")
        if value:
            has_api_key = True

        if not has_api_key:
            env_settings = get_settings()
            if env_settings.openrouter_api_key:
                has_api_key = True

        project_count = await self._project_repo.count_non_demo_projects()

        return SetupStatusResponse(
            has_api_key=has_api_key,
            has_projects=project_count > 0,
            project_count=project_count,
        )

    async def get_api_key_status(self) -> ApiKeyStatusResponse:
        """Check whether an API key is configured and its source."""
        value = await self._settings_repo.get_setting("openrouter_api_key")
        if value:
            return ApiKeyStatusResponse(configured=True, source="database")

        env_settings = get_settings()
        if env_settings.openrouter_api_key:
            return ApiKeyStatusResponse(configured=True, source="environment")

        return ApiKeyStatusResponse(configured=False, source=None)

    async def store_api_key(self, key: str, now: str) -> None:
        """Persist an API key."""
        await self._settings_repo.upsert_setting("openrouter_api_key", key, now)

    async def delete_api_key(self) -> None:
        """Remove a stored API key."""
        await self._settings_repo.delete_setting("openrouter_api_key")
