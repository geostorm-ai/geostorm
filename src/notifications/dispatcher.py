"""Route alerts to configured notification channels."""

from __future__ import annotations

import logging

from src.config import Settings, get_settings
from src.models import Alert, AlertChannel, AlertSeverity, AlertType
from src.notifications.email import SmtpSettings, send_email_alert
from src.notifications.slack import send_slack_alert
from src.notifications.webhook import send_webhook_alert
from src.services.alert_service import (
    SEVERITY_ORDER,
    get_alert,
    get_alert_configs,
    get_project_name,
)

logger = logging.getLogger(__name__)


def _severity_meets_minimum(severity: AlertSeverity, min_severity: AlertSeverity) -> bool:
    """Return True if severity >= min_severity in ordering INFO < WARNING < CRITICAL."""
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[min_severity]


def _type_matches(alert_type: AlertType, allowed_types: list[AlertType]) -> bool:
    """Return True if alert_type is in allowed_types, or allowed_types is empty (accept all)."""
    return len(allowed_types) == 0 or alert_type in allowed_types


async def _send_to_channel(
    channel: AlertChannel,
    alert: Alert,
    endpoint: str,
    project_name: str,
    settings: Settings,
) -> None:
    """Send a single alert to the appropriate channel."""
    if channel == AlertChannel.SLACK:
        await send_slack_alert(alert, endpoint, project_name)

    elif channel == AlertChannel.EMAIL:
        smtp_settings = SmtpSettings(
            host=settings.smtp_host or "",
            port=settings.smtp_port,
            user=settings.smtp_user or "",
            password=settings.smtp_password or "",
            from_addr=settings.smtp_from or "",
        )
        await send_email_alert(alert, smtp_settings, endpoint, project_name)

    elif channel == AlertChannel.WEBHOOK:
        await send_webhook_alert(alert, endpoint, project_name)

    elif channel == AlertChannel.IN_APP:
        logger.debug("In-app alert %s stored (no push delivery)", alert.id)

    else:
        logger.warning("Unknown alert channel %s, skipping", channel)


async def _dispatch_with_fallback(
    alert_ids: list[str],
    project_name: str,
    settings: Settings,
) -> None:
    """Send alerts via env Slack webhook when no configs exist."""
    for alert_id in alert_ids:
        alert = await get_alert(alert_id)
        if not alert:
            continue
        try:
            await send_slack_alert(alert, settings.slack_webhook_url or "", project_name)
        except Exception:
            logger.exception("Slack fallback failed for alert %s", alert_id)


async def dispatch_alerts(project_id: str, alert_ids: list[str]) -> None:
    """Dispatch notifications for a list of alert IDs.

    Loads alert configs for the project, checks type/severity filters,
    and sends to matching channels. Falls back to env-based Slack webhook
    if no configs exist. Errors are logged but never raised.
    """
    if not alert_ids:
        return

    configs = await get_alert_configs(project_id)
    settings = get_settings()
    project_name = await get_project_name(project_id)

    # Fallback: if no configs but slack_webhook_url is set in env, use that
    if not configs and settings.slack_webhook_url:
        logger.info("No alert configs for project %s, using env Slack webhook fallback", project_id)
        await _dispatch_with_fallback(alert_ids, project_name, settings)
        return

    if not configs:
        logger.debug("No alert configs and no env fallback for project %s, skipping dispatch", project_id)
        return

    enabled_configs = [c for c in configs if c.is_enabled]
    if not enabled_configs:
        logger.debug("All alert configs disabled for project %s", project_id)
        return

    for alert_id in alert_ids:
        alert = await get_alert(alert_id)
        if not alert:
            logger.warning("Alert %s not found, skipping dispatch", alert_id)
            continue

        for config in enabled_configs:
            if not _type_matches(alert.alert_type, config.alert_types):
                continue
            if not _severity_meets_minimum(alert.severity, config.min_severity):
                continue

            try:
                await _send_to_channel(config.channel, alert, config.endpoint, project_name, settings)
            except Exception:
                logger.exception(
                    "Failed to send alert %s via %s to %s",
                    alert_id,
                    config.channel,
                    config.endpoint,
                )
