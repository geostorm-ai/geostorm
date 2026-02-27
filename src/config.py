"""Application configuration loaded from environment variables via pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """GeoStorm configuration — all fields optional so the app starts with zero env vars."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # LLM provider API keys (all optional)
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Alert delivery (all optional)
    slack_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    # Telemetry
    no_telemetry: bool = False
    posthog_project_api_key: str | None = None
    posthog_host: str = "https://eu.i.posthog.com"

    # Application
    secret_key: str = "dev-secret-key-change-in-production"
    database_url: str = "./data/geo-storm.db"

    # Version info (set via Docker build args or environment)
    app_version: str | None = None
    build_time: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance populated from environment variables."""
    return Settings()
