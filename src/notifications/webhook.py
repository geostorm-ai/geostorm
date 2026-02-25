"""Generic webhook notification sender."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx
import logfire

if TYPE_CHECKING:
    from src.models import Alert

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0
_TIMEOUT = 10.0


def _build_payload(alert: Alert, project_name: str) -> dict[str, object]:
    """Build the JSON payload for the webhook."""
    payload: dict[str, object] = {
        "event": "alert",
        "project_name": project_name,
        "alert": {
            "id": alert.id,
            "project_id": alert.project_id,
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "is_acknowledged": alert.is_acknowledged,
            "created_at": alert.created_at.isoformat(),
        },
    }

    if alert.metadata:
        payload["metadata"] = alert.metadata.model_dump(exclude_none=True)

    if alert.explanation:
        alert_dict = payload["alert"]
        if isinstance(alert_dict, dict):
            alert_dict["explanation"] = alert.explanation

    return payload


async def send_webhook_alert(alert: Alert, webhook_url: str, project_name: str) -> bool:
    """Send an alert to a generic webhook endpoint via HTTP POST.

    Returns True on success, False on failure. Never raises.
    """
    with logfire.span('webhook notification', alert_id=alert.id):
        payload = _build_payload(alert, project_name)
        headers = {
            "Content-Type": "application/json",
            "X-GeoStorm-Event": "alert",
        }

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    response = await client.post(webhook_url, json=payload, headers=headers)
                if 200 <= response.status_code < 300:  # noqa: PLR2004
                    logger.info("Webhook alert sent for alert_id=%s", alert.id)
                    return True
                logger.warning(
                    "Webhook returned %d on attempt %d/%d: %s",
                    response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    response.text[:200],
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Webhook request failed on attempt %d/%d",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc_info=True,
                )

            if attempt < _MAX_RETRIES - 1:
                delay = _BASE_DELAY * (2**attempt)
                await asyncio.sleep(delay)

        logger.error("Failed to send webhook alert after %d attempts for alert_id=%s", _MAX_RETRIES, alert.id)
        return False
