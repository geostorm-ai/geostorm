"""Tests for notification channels and the alert dispatcher."""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite

from src.models import (
    Alert,
    AlertChannel,
    AlertConfig,
    AlertMetadata,
    AlertSeverity,
    AlertType,
)
from src.notifications.dispatcher import (
    _severity_meets_minimum,
    _type_matches,
    dispatch_alerts,
)
from src.notifications.email import SmtpSettings, send_email_alert
from src.notifications.slack import send_slack_alert
from src.notifications.webhook import send_webhook_alert

_D = "src.notifications.dispatcher"
_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"


def _fake_db_conn(db_path: str):
    """Create an async context manager that returns a real aiosqlite connection to db_path."""

    @contextlib.asynccontextmanager
    async def _ctx():
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row
            yield db
        finally:
            await db.close()

    return _ctx


def _make_alert(**overrides) -> Alert:
    """Create a test alert with sensible defaults."""
    defaults = {
        "id": "alert-1",
        "project_id": "proj-1",
        "alert_type": AlertType.COMPETITOR_EMERGENCE,
        "severity": AlertSeverity.CRITICAL,
        "title": "New competitor detected: Acme",
        "message": "Acme now appears in AI recommendations",
        "metadata": AlertMetadata(competitor_name="Acme", current_value=0.3),
        "is_acknowledged": False,
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return Alert(**defaults)


def _make_smtp_settings() -> SmtpSettings:
    return SmtpSettings(
        host="smtp.test.com",
        port=587,
        user="user@test.com",
        password="secret",
        from_addr="alerts@test.com",
    )


# ---------------------------------------------------------------------------
# Slack notification tests
# ---------------------------------------------------------------------------


class TestSendSlackAlert:
    async def test_successful_send(self):
        alert = _make_alert()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.notifications.slack.httpx.AsyncClient", return_value=mock_client):
            result = await send_slack_alert(alert, "https://hooks.slack.com/test", "Test Project")

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"
        payload = call_args[1]["json"]
        assert "blocks" in payload
        assert "text" in payload

    async def test_non_200_returns_false(self):
        alert = _make_alert()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.notifications.slack.httpx.AsyncClient", return_value=mock_client),
            patch("src.notifications.slack.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_slack_alert(alert, "https://hooks.slack.com/test", "Test Project")

        assert result is False

    async def test_retry_succeeds_on_second_attempt(self):
        alert = _make_alert()

        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Error"

        ok_response = MagicMock()
        ok_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.side_effect = [fail_response, ok_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.notifications.slack.httpx.AsyncClient", return_value=mock_client),
            patch("src.notifications.slack.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_slack_alert(alert, "https://hooks.slack.com/test", "Test Project")

        assert result is True
        assert mock_client.post.call_count == 2

    async def test_exception_retries_then_fails(self):
        alert = _make_alert()

        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.notifications.slack.httpx.AsyncClient", return_value=mock_client),
            patch("src.notifications.slack.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_slack_alert(alert, "https://hooks.slack.com/test", "Test Project")

        assert result is False
        assert mock_client.post.call_count == 3


# ---------------------------------------------------------------------------
# Email notification tests
# ---------------------------------------------------------------------------


class TestSendEmailAlert:
    async def test_successful_send(self):
        alert = _make_alert()
        smtp_settings = _make_smtp_settings()

        with patch("src.notifications.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await send_email_alert(alert, smtp_settings, "recipient@test.com", "Test Project")

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["hostname"] == "smtp.test.com"
        assert call_kwargs["port"] == 587
        # Verify the message object was passed as first positional arg
        msg = mock_send.call_args[0][0]
        assert "[CRITICAL]" in msg["Subject"]
        assert "Acme" in msg["Subject"]
        assert msg["To"] == "recipient@test.com"
        assert msg["From"] == "alerts@test.com"

    async def test_smtp_failure_returns_false(self):
        alert = _make_alert()
        smtp_settings = _make_smtp_settings()

        with (
            patch("src.notifications.email.aiosmtplib.send", new_callable=AsyncMock, side_effect=OSError("SMTP error")),
            patch("src.notifications.email.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_email_alert(alert, smtp_settings, "recipient@test.com", "Test Project")

        assert result is False

    async def test_retry_succeeds_on_second_attempt(self):
        alert = _make_alert()
        smtp_settings = _make_smtp_settings()

        with (
            patch(
                "src.notifications.email.aiosmtplib.send",
                new_callable=AsyncMock,
                side_effect=[OSError("fail"), None],
            ) as mock_send,
            patch("src.notifications.email.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_email_alert(alert, smtp_settings, "recipient@test.com", "Test Project")

        assert result is True
        assert mock_send.call_count == 2


# ---------------------------------------------------------------------------
# Webhook notification tests
# ---------------------------------------------------------------------------


class TestSendWebhookAlert:
    async def test_successful_send(self):
        alert = _make_alert()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.notifications.webhook.httpx.AsyncClient", return_value=mock_client):
            result = await send_webhook_alert(alert, "https://webhook.test/hook", "Test Project")

        assert result is True
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["event"] == "alert"
        assert payload["project_name"] == "Test Project"
        assert payload["alert"]["id"] == "alert-1"
        assert payload["alert"]["severity"] == "critical"
        assert payload["alert"]["alert_type"] == "competitor_emergence"
        assert "metadata" in payload
        # Verify custom header
        headers = call_args[1]["headers"]
        assert headers["X-GeoStorm-Event"] == "alert"

    async def test_non_2xx_returns_false(self):
        alert = _make_alert()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.notifications.webhook.httpx.AsyncClient", return_value=mock_client),
            patch("src.notifications.webhook.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook_alert(alert, "https://webhook.test/hook", "Test Project")

        assert result is False

    async def test_retry_succeeds_on_second_attempt(self):
        alert = _make_alert()

        fail_response = MagicMock()
        fail_response.status_code = 503
        fail_response.text = "Unavailable"

        ok_response = MagicMock()
        ok_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.side_effect = [fail_response, ok_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.notifications.webhook.httpx.AsyncClient", return_value=mock_client),
            patch("src.notifications.webhook.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook_alert(alert, "https://webhook.test/hook", "Test Project")

        assert result is True
        assert mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# Dispatcher helper tests
# ---------------------------------------------------------------------------


class TestSeverityMeetsMinimum:
    def test_info_meets_info(self):
        assert _severity_meets_minimum(AlertSeverity.INFO, AlertSeverity.INFO) is True

    def test_warning_meets_info(self):
        assert _severity_meets_minimum(AlertSeverity.WARNING, AlertSeverity.INFO) is True

    def test_critical_meets_warning(self):
        assert _severity_meets_minimum(AlertSeverity.CRITICAL, AlertSeverity.WARNING) is True

    def test_info_does_not_meet_warning(self):
        assert _severity_meets_minimum(AlertSeverity.INFO, AlertSeverity.WARNING) is False

    def test_warning_does_not_meet_critical(self):
        assert _severity_meets_minimum(AlertSeverity.WARNING, AlertSeverity.CRITICAL) is False


class TestTypeMatches:
    def test_empty_allowed_accepts_all(self):
        assert _type_matches(AlertType.COMPETITOR_EMERGENCE, []) is True

    def test_matching_type(self):
        assert _type_matches(AlertType.DISAPPEARANCE, [AlertType.DISAPPEARANCE, AlertType.MODEL_DIVERGENCE]) is True

    def test_non_matching_type(self):
        assert _type_matches(AlertType.COMPETITOR_EMERGENCE, [AlertType.DISAPPEARANCE]) is False


# ---------------------------------------------------------------------------
# dispatch_alerts integration tests
# ---------------------------------------------------------------------------


class TestDispatchAlerts:
    async def test_severity_filter_skips_info_for_warning_config(self):
        """Config with min_severity=WARNING should skip INFO alerts but deliver WARNING and CRITICAL."""
        info_alert = _make_alert(id="alert-info", severity=AlertSeverity.INFO)
        warning_alert = _make_alert(id="alert-warn", severity=AlertSeverity.WARNING)
        critical_alert = _make_alert(id="alert-crit", severity=AlertSeverity.CRITICAL)

        now = datetime.now(tz=UTC)
        config = AlertConfig(
            id="cfg-1",
            project_id="proj-1",
            channel=AlertChannel.SLACK,
            endpoint="https://hooks.slack.com/test",
            alert_types=[],
            min_severity=AlertSeverity.WARNING,
            is_enabled=True,
            created_at=now,
            updated_at=now,
        )

        alert_map = {
            "alert-info": info_alert,
            "alert-warn": warning_alert,
            "alert-crit": critical_alert,
        }

        with (
            patch(f"{_D}.get_alert_configs", new_callable=AsyncMock, return_value=[config]),
            patch(f"{_D}.get_alert", new_callable=AsyncMock, side_effect=alert_map.get),
            patch(f"{_D}.get_project_name", new_callable=AsyncMock, return_value="Test Project"),
            patch(f"{_D}.get_settings") as mock_settings,
            patch(f"{_D}.send_slack_alert", new_callable=AsyncMock, return_value=True) as mock_slack,
        ):
            mock_settings.return_value.slack_webhook_url = None
            await dispatch_alerts("proj-1", ["alert-info", "alert-warn", "alert-crit"])

        # INFO should be skipped, WARNING and CRITICAL should be sent
        assert mock_slack.call_count == 2
        sent_ids = [call.args[0].id for call in mock_slack.call_args_list]
        assert "alert-info" not in sent_ids
        assert "alert-warn" in sent_ids
        assert "alert-crit" in sent_ids

    async def test_type_filter_skips_non_matching(self):
        """Config with specific alert_types should skip non-matching alert types."""
        matching_alert = _make_alert(id="alert-match", alert_type=AlertType.COMPETITOR_EMERGENCE)
        non_matching_alert = _make_alert(id="alert-skip", alert_type=AlertType.POSITION_DEGRADATION)

        now = datetime.now(tz=UTC)
        config = AlertConfig(
            id="cfg-1",
            project_id="proj-1",
            channel=AlertChannel.WEBHOOK,
            endpoint="https://webhook.test/hook",
            alert_types=[AlertType.COMPETITOR_EMERGENCE, AlertType.DISAPPEARANCE],
            min_severity=AlertSeverity.INFO,
            is_enabled=True,
            created_at=now,
            updated_at=now,
        )

        alert_map = {
            "alert-match": matching_alert,
            "alert-skip": non_matching_alert,
        }

        with (
            patch(f"{_D}.get_alert_configs", new_callable=AsyncMock, return_value=[config]),
            patch(f"{_D}.get_alert", new_callable=AsyncMock, side_effect=alert_map.get),
            patch(f"{_D}.get_project_name", new_callable=AsyncMock, return_value="Test Project"),
            patch(f"{_D}.get_settings") as mock_settings,
            patch(f"{_D}.send_webhook_alert", new_callable=AsyncMock, return_value=True) as mock_webhook,
        ):
            mock_settings.return_value.slack_webhook_url = None
            await dispatch_alerts("proj-1", ["alert-match", "alert-skip"])

        assert mock_webhook.call_count == 1
        assert mock_webhook.call_args[0][0].id == "alert-match"

    async def test_disabled_config_is_skipped(self):
        """Disabled configs should be skipped entirely."""
        alert = _make_alert()

        now = datetime.now(tz=UTC)
        disabled_config = AlertConfig(
            id="cfg-disabled",
            project_id="proj-1",
            channel=AlertChannel.SLACK,
            endpoint="https://hooks.slack.com/test",
            alert_types=[],
            min_severity=AlertSeverity.INFO,
            is_enabled=False,
            created_at=now,
            updated_at=now,
        )

        with (
            patch(f"{_D}.get_alert_configs", new_callable=AsyncMock, return_value=[disabled_config]),
            patch(f"{_D}.get_alert", new_callable=AsyncMock, return_value=alert),
            patch(f"{_D}.get_project_name", new_callable=AsyncMock, return_value="Test Project"),
            patch(f"{_D}.get_settings") as mock_settings,
            patch(f"{_D}.send_slack_alert", new_callable=AsyncMock) as mock_slack,
        ):
            mock_settings.return_value.slack_webhook_url = None
            await dispatch_alerts("proj-1", ["alert-1"])

        mock_slack.assert_not_called()

    async def test_empty_alert_ids_returns_immediately(self):
        with patch(f"{_D}.get_alert_configs", new_callable=AsyncMock) as mock_configs:
            await dispatch_alerts("proj-1", [])

        mock_configs.assert_not_called()

    async def test_fallback_to_env_slack_webhook(self):
        """When no configs exist but env slack_webhook_url is set, use fallback."""
        alert = _make_alert()

        with (
            patch(f"{_D}.get_alert_configs", new_callable=AsyncMock, return_value=[]),
            patch(f"{_D}.get_alert", new_callable=AsyncMock, return_value=alert),
            patch(f"{_D}.get_project_name", new_callable=AsyncMock, return_value="Test Project"),
            patch(f"{_D}.get_settings") as mock_settings,
            patch(f"{_D}.send_slack_alert", new_callable=AsyncMock, return_value=True) as mock_slack,
        ):
            mock_settings.return_value.slack_webhook_url = "https://hooks.slack.com/fallback"
            await dispatch_alerts("proj-1", ["alert-1"])

        mock_slack.assert_called_once()
        assert mock_slack.call_args[0][1] == "https://hooks.slack.com/fallback"

    async def test_multiple_configs_receive_matching_alerts(self):
        """Multiple enabled configs should each receive matching alerts."""
        alert = _make_alert()

        now = datetime.now(tz=UTC)
        slack_config = AlertConfig(
            id="cfg-slack",
            project_id="proj-1",
            channel=AlertChannel.SLACK,
            endpoint="https://hooks.slack.com/test",
            alert_types=[],
            min_severity=AlertSeverity.INFO,
            is_enabled=True,
            created_at=now,
            updated_at=now,
        )
        webhook_config = AlertConfig(
            id="cfg-webhook",
            project_id="proj-1",
            channel=AlertChannel.WEBHOOK,
            endpoint="https://webhook.test/hook",
            alert_types=[],
            min_severity=AlertSeverity.INFO,
            is_enabled=True,
            created_at=now,
            updated_at=now,
        )

        with (
            patch(f"{_D}.get_alert_configs", new_callable=AsyncMock, return_value=[slack_config, webhook_config]),
            patch(f"{_D}.get_alert", new_callable=AsyncMock, return_value=alert),
            patch(f"{_D}.get_project_name", new_callable=AsyncMock, return_value="Test Project"),
            patch(f"{_D}.get_settings") as mock_settings,
            patch(f"{_D}.send_slack_alert", new_callable=AsyncMock, return_value=True) as mock_slack,
            patch(f"{_D}.send_webhook_alert", new_callable=AsyncMock, return_value=True) as mock_webhook,
        ):
            mock_settings.return_value.slack_webhook_url = None
            await dispatch_alerts("proj-1", ["alert-1"])

        mock_slack.assert_called_once()
        mock_webhook.assert_called_once()
