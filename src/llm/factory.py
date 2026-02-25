"""LLM provider factory and API key resolution."""

import logging

import logfire

from src.config import get_settings
from src.database import get_db_connection
from src.llm.base import BaseLLMProvider, ProviderType
from src.llm.openrouter import OpenRouterProvider

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
            async with get_db_connection() as db:
                cursor = await db.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    (db_key,),
                )
                row = await cursor.fetchone()
                if row:
                    value = row[0]
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        except Exception:  # noqa: BLE001
            logger.debug("Could not read API key from database for %s", provider_type)

    env_attr = _PROVIDER_KEY_MAP.get(provider_type)
    if env_attr:
        settings = get_settings()
        env_value: str | None = getattr(settings, env_attr, None)
        if isinstance(env_value, str) and env_value.strip():
            return env_value.strip()

    return None


async def create_provider(provider_type: ProviderType) -> BaseLLMProvider | None:
    """Create a provider instance if an API key is available."""
    api_key = await get_api_key(provider_type)
    if not api_key:
        return None

    if provider_type == ProviderType.OPENROUTER:
        logfire.info('created LLM provider', provider=provider_type.value)
        return OpenRouterProvider(api_key)

    # Future: add OPENAI, ANTHROPIC, GOOGLE providers here
    logger.warning("Provider %s is not yet implemented", provider_type)
    return None


async def get_available_providers() -> list[ProviderType]:
    """Return list of provider types that have configured API keys."""
    all_setting_keys = list(_PROVIDER_KEY_MAP.values())
    db_keys: set[str] = set()

    try:
        placeholders = ", ".join("?" for _ in all_setting_keys)
        async with get_db_connection() as db:
            cursor = await db.execute(
                f"SELECT key FROM settings WHERE key IN ({placeholders}) AND value IS NOT NULL AND value != ''",
                all_setting_keys,
            )
            db_keys = {row[0] for row in await cursor.fetchall()}
    except Exception:  # noqa: BLE001
        logger.debug("Could not read API keys from database")

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
