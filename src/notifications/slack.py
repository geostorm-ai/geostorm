"""Slack webhook notification sender."""

from __future__ import annotations

import asyncio
import logging

import httpx

from src.models import Alert, AlertSeverity

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0
_TIMEOUT = 10.0

_SEVERITY_EMOJI: dict[AlertSeverity, str] = {
    AlertSeverity.CRITICAL: ":red_circle:",
    AlertSeverity.WARNING: ":warning:",
    AlertSeverity.INFO: ":information_source:",
}


def _build_blocks(alert: Alert, project_name: str) -> list[dict[str, object]]:
    """Build Slack Block Kit blocks for the alert message."""
    emoji = _SEVERITY_EMOJI.get(alert.severity, ":information_source:")
    severity_label = alert.severity.value.upper()

    blocks: list[dict[str, object]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} [{severity_label}] {alert.title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{alert.title}*\n{alert.message}",
            },
        },
    ]

    context_elements: list[dict[str, str]] = [
        {"type": "mrkdwn", "text": f"*Project:* {project_name}"},
        {"type": "mrkdwn", "text": f"*Type:* {alert.alert_type.value}"},
        {"type": "mrkdwn", "text": f"*Alert ID:* {alert.id}"},
    ]
    blocks.append({"type": "context", "elements": context_elements})

    if alert.metadata:
        fields: list[str] = []
        if alert.metadata.current_value is not None:
            fields.append(f"*Current:* {alert.metadata.current_value}")
        if alert.metadata.previous_value is not None:
            fields.append(f"*Previous:* {alert.metadata.previous_value}")
        if alert.metadata.threshold is not None:
            fields.append(f"*Threshold:* {alert.metadata.threshold}")
        if alert.metadata.competitor_name:
            fields.append(f"*Competitor:* {alert.metadata.competitor_name}")
        if fields:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "\n".join(fields)},
                },
            )

    return blocks


async def send_slack_alert(alert: Alert, webhook_url: str, project_name: str) -> bool:
    """Send an alert to a Slack channel via incoming webhook.

    Returns True on success, False on failure. Never raises.
    """
    payload: dict[str, object] = {
        "blocks": _build_blocks(alert, project_name),
        "text": f"[{alert.severity.value.upper()}] {alert.title}",
    }

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(webhook_url, json=payload)
            if response.status_code == 200:  # noqa: PLR2004
                logger.info("Slack alert sent for alert_id=%s", alert.id)
                return True
            logger.warning(
                "Slack webhook returned %d on attempt %d/%d: %s",
                response.status_code,
                attempt + 1,
                _MAX_RETRIES,
                response.text[:200],
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Slack webhook request failed on attempt %d/%d",
                attempt + 1,
                _MAX_RETRIES,
                exc_info=True,
            )

        if attempt < _MAX_RETRIES - 1:
            delay = _BASE_DELAY * (2**attempt)
            await asyncio.sleep(delay)

    logger.error("Failed to send Slack alert after %d attempts for alert_id=%s", _MAX_RETRIES, alert.id)
    return False
