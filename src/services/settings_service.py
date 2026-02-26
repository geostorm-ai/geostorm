"""Service layer for application settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.config import get_settings
from src.schemas import ApiKeyStatusResponse, SetupStatusResponse

if TYPE_CHECKING:
    from src.repos.project_repo import ProjectRepo
    from src.repos.settings_repo import SettingsRepo

logger = logging.getLogger(__name__)

# Cheap model on OpenRouter for key validation
_VALIDATION_MODEL = "google/gemini-2.5-flash-lite"


_AUTH_ERROR_MSG = (
    "Invalid API key. Please check that you're using a valid OpenRouter API key (starts with sk-or-)."
)


class InvalidApiKeyError(Exception):
    """Raised when an API key fails validation against OpenRouter."""

    def __init__(self, message: str = _AUTH_ERROR_MSG) -> None:
        self.message = message
        super().__init__(message)


async def validate_openrouter_key(api_key: str) -> None:
    """Validate an OpenRouter API key by sending a tiny prompt via Pydantic AI.

    Uses the cheapest available model to verify the key actually works end-to-end.
    Raises InvalidApiKeyError if the key is rejected.
    """
    try:
        provider = OpenRouterProvider(api_key=api_key)
        model = OpenAIChatModel(_VALIDATION_MODEL, provider=provider)
        agent: Agent[None, str] = Agent(model)
        await agent.run("Hi")
    except Exception as exc:
        err = str(exc)
        if "401" in err or "auth" in err.lower() or "Missing Authentication" in err:
            logger.warning("OpenRouter API key validation failed: %s", err)
            raise InvalidApiKeyError from exc
        logger.warning("OpenRouter API key validation error: %s", err)
        raise InvalidApiKeyError(f"Could not validate API key: {err}") from exc  # noqa: TRY003


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
        """Validate and persist an API key.

        Raises InvalidApiKeyError if the key is rejected by OpenRouter.
        """
        await validate_openrouter_key(key)
        await self._settings_repo.upsert_setting("openrouter_api_key", key, now)

    async def delete_api_key(self) -> None:
        """Remove a stored API key."""
        await self._settings_repo.delete_setting("openrouter_api_key")
