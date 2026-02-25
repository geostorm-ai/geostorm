"""Email notification sender via SMTP."""

from __future__ import annotations

import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import aiosmtplib
import logfire
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.models import Alert

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


class SmtpSettings(BaseModel):
    """SMTP connection settings for sending alert emails."""

    host: str
    port: int = 587
    user: str
    password: str
    from_addr: str


def _build_plain_body(alert: Alert, project_name: str) -> str:
    """Build plain-text email body."""
    lines = [
        f"[{alert.severity.value.upper()}] {alert.title}",
        "",
        alert.message,
        "",
        f"Project: {project_name}",
        f"Alert Type: {alert.alert_type.value}",
        f"Alert ID: {alert.id}",
    ]
    if alert.metadata:
        if alert.metadata.current_value is not None:
            lines.append(f"Current Value: {alert.metadata.current_value}")
        if alert.metadata.previous_value is not None:
            lines.append(f"Previous Value: {alert.metadata.previous_value}")
        if alert.metadata.threshold is not None:
            lines.append(f"Threshold: {alert.metadata.threshold}")
        if alert.metadata.competitor_name:
            lines.append(f"Competitor: {alert.metadata.competitor_name}")
    return "\n".join(lines)


def _build_html_body(alert: Alert, project_name: str) -> str:
    """Build HTML email body."""
    severity = alert.severity.value.upper()
    meta_rows = ""
    if alert.metadata:
        items: list[str] = []
        if alert.metadata.current_value is not None:
            items.append(f"<tr><td><strong>Current Value</strong></td><td>{alert.metadata.current_value}</td></tr>")
        if alert.metadata.previous_value is not None:
            items.append(f"<tr><td><strong>Previous Value</strong></td><td>{alert.metadata.previous_value}</td></tr>")
        if alert.metadata.threshold is not None:
            items.append(f"<tr><td><strong>Threshold</strong></td><td>{alert.metadata.threshold}</td></tr>")
        if alert.metadata.competitor_name:
            items.append(f"<tr><td><strong>Competitor</strong></td><td>{alert.metadata.competitor_name}</td></tr>")
        if items:
            meta_rows = "<table>" + "".join(items) + "</table>"

    return (
        f"<h2>[{severity}] {alert.title}</h2>"
        f"<p>{alert.message}</p>"
        f"<p><strong>Project:</strong> {project_name}<br>"
        f"<strong>Type:</strong> {alert.alert_type.value}<br>"
        f"<strong>Alert ID:</strong> {alert.id}</p>"
        f"{meta_rows}"
    )


async def send_email_alert(
    alert: Alert,
    smtp_settings: SmtpSettings,
    recipient: str,
    project_name: str,
) -> bool:
    """Send an alert email via SMTP.

    Returns True on success, False on failure. Never raises.
    """
    with logfire.span('email notification', alert_id=alert.id):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
        msg["From"] = smtp_settings.from_addr
        msg["To"] = recipient

        msg.attach(MIMEText(_build_plain_body(alert, project_name), "plain"))
        msg.attach(MIMEText(_build_html_body(alert, project_name), "html"))

        for attempt in range(_MAX_RETRIES):
            try:
                await aiosmtplib.send(
                    msg,
                    hostname=smtp_settings.host,
                    port=smtp_settings.port,
                    username=smtp_settings.user,
                    password=smtp_settings.password,
                    start_tls=True,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Email send failed on attempt %d/%d",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc_info=True,
                )
            else:
                logger.info("Email alert sent to %s for alert_id=%s", recipient, alert.id)
                return True

            if attempt < _MAX_RETRIES - 1:
                delay = _BASE_DELAY * (2**attempt)
                await asyncio.sleep(delay)

        logger.error("Failed to send email alert after %d attempts for alert_id=%s", _MAX_RETRIES, alert.id)
        return False
