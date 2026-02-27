"""Tests for the anonymous analytics module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

import src.analytics as analytics_mod
from src.analytics import (
    capture_run_completed,
    capture_server_started,
    init_analytics,
    shutdown_analytics,
)

_FAKE_KEY = "phc_test_key"
_FAKE_HOST = "https://eu.i.posthog.com"


def _mock_settings(*, no_telemetry=False, api_key=_FAKE_KEY, host=_FAKE_HOST):
    mock = MagicMock()
    mock.no_telemetry = no_telemetry
    mock.posthog_project_api_key = api_key
    mock.posthog_host = host
    return mock


@pytest.fixture(autouse=True)
def _reset_analytics():
    """Reset module-level state before each test."""
    analytics_mod._posthog_client = None
    analytics_mod._server_id = None
    yield
    analytics_mod._posthog_client = None
    analytics_mod._server_id = None


@pytest.fixture
def mock_posthog():
    """Provide a mock PostHog client and patch the import."""
    mock_client = MagicMock()
    mock_class = MagicMock(return_value=mock_client)

    mock_module = MagicMock()
    mock_module.Posthog = mock_class

    with patch.dict(sys.modules, {"posthog": mock_module}):
        yield mock_client, mock_class


class TestInitAnalytics:
    def test_creates_client(self, mock_posthog):
        _mock_client, mock_class = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("test-server-id")

        mock_class.assert_called_once()
        call_kwargs = mock_class.call_args[1]
        assert call_kwargs["project_api_key"] == _FAKE_KEY
        assert call_kwargs["host"] == _FAKE_HOST
        assert call_kwargs["disable_geoip"] is True
        assert analytics_mod._server_id == "test-server-id"

    def test_no_telemetry_skips_init(self, mock_posthog):
        _mock_client, mock_class = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings(no_telemetry=True)):
            init_analytics("test-server-id")

        mock_class.assert_not_called()
        assert analytics_mod._posthog_client is None

    def test_no_api_key_skips_init(self, mock_posthog):
        _mock_client, mock_class = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings(api_key=None)):
            init_analytics("test-server-id")

        mock_class.assert_not_called()
        assert analytics_mod._posthog_client is None

    def test_missing_posthog_package(self):
        with (
            patch("src.analytics.get_settings", return_value=_mock_settings()),
            patch.dict(sys.modules, {"posthog": None}),
        ):
            init_analytics("test-server-id")

        assert analytics_mod._posthog_client is None
        assert analytics_mod._server_id is None


class TestCaptureEvents:
    def test_server_started_sends_event(self, mock_posthog):
        mock_client, _ = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("srv-123")

        capture_server_started()

        mock_client.capture.assert_called_once()
        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["distinct_id"] == "srv-123"
        assert call_kwargs["event"] == "server_started"
        assert call_kwargs["properties"]["$ip"] is None
        assert call_kwargs["disable_geoip"] is True

    def test_run_completed_sends_event(self, mock_posthog):
        mock_client, _ = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("srv-456")

        capture_run_completed()

        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["distinct_id"] == "srv-456"
        assert call_kwargs["event"] == "run_completed"
        assert call_kwargs["properties"]["$ip"] is None
        assert call_kwargs["disable_geoip"] is True

    def test_no_extra_properties(self, mock_posthog):
        mock_client, _ = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("srv-789")

        capture_server_started()
        capture_run_completed()

        for call in mock_client.capture.call_args_list:
            props = call[1]["properties"]
            # Only $ip should be present (set to None)
            assert props == {"$ip": None}

    def test_noop_when_not_initialized(self):
        # Should not raise
        capture_server_started()
        capture_run_completed()


class TestShutdown:
    def test_shutdown_calls_client(self, mock_posthog):
        mock_client, _ = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("srv-000")

        shutdown_analytics()

        mock_client.shutdown.assert_called_once()
        assert analytics_mod._posthog_client is None
        assert analytics_mod._server_id is None

    def test_shutdown_noop_when_not_initialized(self):
        # Should not raise
        shutdown_analytics()

    def test_shutdown_handles_exception(self, mock_posthog):
        mock_client, _ = mock_posthog

        with patch("src.analytics.get_settings", return_value=_mock_settings()):
            init_analytics("srv-err")

        mock_client.shutdown.side_effect = RuntimeError("flush failed")
        shutdown_analytics()

        assert analytics_mod._posthog_client is None


class TestNoTelemetryEnv:
    def test_no_events_when_disabled(self):
        """When NO_TELEMETRY=true, nothing is sent even if posthog is available."""
        with patch("src.analytics.get_settings", return_value=_mock_settings(no_telemetry=True)):
            init_analytics("srv-disabled")

        capture_server_started()
        capture_run_completed()

        assert analytics_mod._posthog_client is None
