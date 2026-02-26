"""LLM model factory and API key resolution."""

import logging

import logfire
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.config import get_settings
from src.container import settings_repo
from src.llm.base import LLMError, ProviderType

logger = logging.getLogger(__name__)

_PROVIDER_KEY_MAP: dict[ProviderType, str] = {
    ProviderType.OPENROUTER: "openrouter_api_key",
    ProviderType.OPENAI: "openai_api_key",
    ProviderType.ANTHROPIC: "anthropic_api_key",
    ProviderType.GOOGLE: "google_api_key",
}


async def get_api_key(provider_type: ProviderType) -> str | None:
    """Get API key for a provider. Checks SQLite settings first, then env vars."""
    db_key = _PROVIDER_KEY_MAP.get(provider_type)
    if db_key:
        try:
            value = await settings_repo.get_setting(db_key)
            if value and value.strip():
                return value.strip()
        except Exception:  # noqa: BLE001
            logger.warning("Could not read API key from database for %s", provider_type, exc_info=True)

    env_attr = _PROVIDER_KEY_MAP.get(provider_type)
    if env_attr:
        settings = get_settings()
        env_value: str | None = getattr(settings, env_attr, None)
        if isinstance(env_value, str) and env_value.strip():
            return env_value.strip()

    return None


async def create_model(provider_type: ProviderType, model_id: str) -> OpenAIChatModel:
    """Create a Pydantic AI model for the given provider and model ID."""
    api_key = await get_api_key(provider_type)
    if not api_key:
        msg = f"No API key configured for {provider_type}"
        raise LLMError(msg, provider=provider_type)

    if provider_type == ProviderType.OPENROUTER:
        logfire.info("created LLM model", provider=provider_type.value, model=model_id)
        return OpenAIChatModel(model_id, provider=OpenRouterProvider(api_key=api_key))

    msg = f"Provider {provider_type} is not yet implemented"
    raise LLMError(msg, provider=provider_type)


async def get_available_providers() -> list[ProviderType]:
    """Return list of provider types that have configured API keys."""
    all_setting_keys = list(_PROVIDER_KEY_MAP.values())

    try:
        db_keys = await settings_repo.get_configured_keys(all_setting_keys)
    except Exception:  # noqa: BLE001
        logger.debug("Could not read API keys from database")
        db_keys = set()

    settings = get_settings()
    available: list[ProviderType] = []
    for provider_type, setting_key in _PROVIDER_KEY_MAP.items():
        if setting_key in db_keys:
            available.append(provider_type)
            continue
        env_value: str | None = getattr(settings, setting_key, None)
        if isinstance(env_value, str) and env_value.strip():
            available.append(provider_type)

    return available
