"""Anonymous analytics via PostHog — privacy-first, zero PII."""

from __future__ import annotations

import logging
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

_posthog_client: Any = None
_server_id: str | None = None

_POSTHOG_API_KEY = "phc_1MOlbfPkjOsIOj9UVWqxrMusGJooMq3LFvuIbCnYEer"
_POSTHOG_HOST = "https://us.i.posthog.com"


def init_analytics(server_id: str) -> None:
    """Initialize the PostHog client with maximum privacy settings."""
    global _posthog_client, _server_id  # noqa: PLW0603

    if get_settings().no_telemetry:
        logger.info("Telemetry disabled via NO_TELEMETRY")
        return

    try:
        from posthog import Posthog  # noqa: PLC0415
    except ImportError:
        logger.debug("posthog package not installed, analytics disabled")
        return

    try:
        client = Posthog(
            project_api_key=_POSTHOG_API_KEY,
            host=_POSTHOG_HOST,
            disable_geoip=True,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to create PostHog client, analytics disabled")
        return

    _server_id = server_id
    _posthog_client = client
    logger.info("Analytics initialized")


def capture_server_started() -> None:
    """Record a server_started event with no properties."""
    if _posthog_client is None or _server_id is None:
        return
    _posthog_client.capture(
        distinct_id=_server_id,
        event="server_started",
        properties={"$ip": None},
        disable_geoip=True,
    )


def capture_run_completed() -> None:
    """Record a run_completed event with no properties."""
    if _posthog_client is None or _server_id is None:
        return
    _posthog_client.capture(
        distinct_id=_server_id,
        event="run_completed",
        properties={"$ip": None},
        disable_geoip=True,
    )


def shutdown_analytics() -> None:
    """Flush pending events and shut down the PostHog client."""
    global _posthog_client, _server_id  # noqa: PLW0603

    if _posthog_client is not None:
        try:
            _posthog_client.shutdown()
        except Exception:  # noqa: BLE001
            logger.debug("Error shutting down analytics client")
        _posthog_client = None
        _server_id = None
