"""Tests for the LLM provider layer."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.llm.base import (
    LLMProviderError,
    PromptRequest,
    PromptResponse,
    ProviderError,
    ProviderType,
)
from src.llm.factory import get_api_key
from src.llm.openrouter import OpenRouterProvider
from src.llm.prompt_service import generate_prompt, get_system_prompt

# ---------------------------------------------------------------------------
# Prompt service tests
# ---------------------------------------------------------------------------


class TestPromptService:
    def test_generate_prompt_default_template(self):
        result = generate_prompt("best Python web framework")
        assert "best Python web framework" in result

    def test_generate_prompt_different_templates(self):
        r0 = generate_prompt("test term", template_index=0)
        r1 = generate_prompt("test term", template_index=1)
        r2 = generate_prompt("test term", template_index=2)
        assert r0 != r1
        assert r1 != r2
        assert "test term" in r0
        assert "test term" in r1
        assert "test term" in r2

    def test_generate_prompt_wraps_index(self):
        r0 = generate_prompt("foo", template_index=0)
        r3 = generate_prompt("foo", template_index=3)
        assert r0 == r3

    def test_get_system_prompt_returns_nonempty(self):
        prompt = get_system_prompt()
        assert len(prompt) > 0
        assert "recommendation" in prompt.lower()


# ---------------------------------------------------------------------------
# BaseLLMProvider retry logic tests
# ---------------------------------------------------------------------------



def _ok_response() -> PromptResponse:
    return PromptResponse(
        text="test response",
        model_id="test-model",
        provider=ProviderType.OPENROUTER,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        latency_ms=100,
        cost_usd=0.001,
    )


def _retryable_error() -> LLMProviderError:
    return LLMProviderError(
        ProviderError(
            code="http_429",
            message="Rate limited",
            provider=ProviderType.OPENROUTER,
            is_retryable=True,
            retry_after_seconds=0,
        ),
    )


def _non_retryable_error() -> LLMProviderError:
    return LLMProviderError(
        ProviderError(
            code="http_401",
            message="Unauthorized",
            provider=ProviderType.OPENROUTER,
            is_retryable=False,
        ),
    )


class TestBaseLLMProviderRetry:
    """Test the retry logic by importing and using the real BaseLLMProvider."""

    async def test_successful_first_attempt(self):
        from src.llm.base import BaseLLMProvider

        class TestProvider(BaseLLMProvider):
            provider_type = ProviderType.OPENROUTER

            def __init__(self):
                self.call_count = 0

            async def _send_request(self, request):
                self.call_count += 1
                return _ok_response()

            async def close(self):
                pass

        provider = TestProvider()
        request = PromptRequest(prompt="test", model_id="model")
        result = await provider.send_prompt(request)

        assert result.text == "test response"
        assert provider.call_count == 1

    async def test_retries_on_retryable_error_then_succeeds(self):
        from src.llm.base import BaseLLMProvider

        class TestProvider(BaseLLMProvider):
            provider_type = ProviderType.OPENROUTER

            def __init__(self):
                self.call_count = 0
                self.items = [_retryable_error(), _ok_response()]

            async def _send_request(self, request):
                idx = self.call_count
                self.call_count += 1
                item = self.items[idx]
                if isinstance(item, LLMProviderError):
                    raise item
                return item

            async def close(self):
                pass

        provider = TestProvider()
        request = PromptRequest(prompt="test", model_id="model")
        result = await provider.send_prompt(request)

        assert result.text == "test response"
        assert provider.call_count == 2

    async def test_retries_3_times_on_retryable_then_raises(self):
        from src.llm.base import BaseLLMProvider

        class TestProvider(BaseLLMProvider):
            provider_type = ProviderType.OPENROUTER

            def __init__(self):
                self.call_count = 0

            async def _send_request(self, request):
                self.call_count += 1
                raise _retryable_error()

            async def close(self):
                pass

        provider = TestProvider()
        request = PromptRequest(prompt="test", model_id="model")

        with pytest.raises(LLMProviderError) as exc_info:
            await provider.send_prompt(request)

        assert exc_info.value.error.is_retryable
        assert provider.call_count == 3

    async def test_no_retry_on_non_retryable_error(self):
        from src.llm.base import BaseLLMProvider

        class TestProvider(BaseLLMProvider):
            provider_type = ProviderType.OPENROUTER

            def __init__(self):
                self.call_count = 0

            async def _send_request(self, request):
                self.call_count += 1
                raise _non_retryable_error()

            async def close(self):
                pass

        provider = TestProvider()
        request = PromptRequest(prompt="test", model_id="model")

        with pytest.raises(LLMProviderError) as exc_info:
            await provider.send_prompt(request)

        assert not exc_info.value.error.is_retryable
        assert provider.call_count == 1


# ---------------------------------------------------------------------------
# OpenRouterProvider tests with mocked httpx
# ---------------------------------------------------------------------------


class TestOpenRouterProvider:
    async def test_successful_request(self):
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Here are my recommendations..."}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 100},
            },
        )

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response):
            request = PromptRequest(prompt="test prompt", model_id="openai/gpt-4o")
            result = await provider._send_request(request)

        assert result.text == "Here are my recommendations..."
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 100
        assert result.total_tokens == 150
        assert result.provider == ProviderType.OPENROUTER

        await provider.close()

    async def test_retryable_error_429(self):
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = httpx.Response(
            429,
            json={"error": {"message": "Rate limit exceeded"}},
        )

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response):
            request = PromptRequest(prompt="test", model_id="openai/gpt-4o")

            with pytest.raises(LLMProviderError) as exc_info:
                await provider._send_request(request)

            assert exc_info.value.error.is_retryable
            assert exc_info.value.error.code == "http_429"

        await provider.close()

    async def test_non_retryable_error_401(self):
        provider = OpenRouterProvider(api_key="bad-key")

        mock_response = httpx.Response(
            401,
            json={"error": {"message": "Invalid API key"}},
        )

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response):
            request = PromptRequest(prompt="test", model_id="openai/gpt-4o")

            with pytest.raises(LLMProviderError) as exc_info:
                await provider._send_request(request)

            assert not exc_info.value.error.is_retryable
            assert exc_info.value.error.code == "http_401"

        await provider.close()

    async def test_retryable_error_500(self):
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = httpx.Response(500, json={"error": "Internal server error"})

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response):
            request = PromptRequest(prompt="test", model_id="model")

            with pytest.raises(LLMProviderError) as exc_info:
                await provider._send_request(request)

            assert exc_info.value.error.is_retryable

        await provider.close()

    async def test_timeout_is_retryable(self):
        provider = OpenRouterProvider(api_key="test-key")

        with patch.object(
            provider._client, "post", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout"),
        ):
            request = PromptRequest(prompt="test", model_id="model")

            with pytest.raises(LLMProviderError) as exc_info:
                await provider._send_request(request)

            assert exc_info.value.error.is_retryable
            assert exc_info.value.error.code == "timeout"

        await provider.close()

    async def test_system_prompt_included_in_messages(self):
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

        captured_payload: dict[str, object] = {}

        async def mock_post(url: str, **kwargs: object) -> httpx.Response:
            captured_payload.update(kwargs)  # type: ignore[arg-type]
            return mock_response

        with patch.object(provider._client, "post", side_effect=mock_post):
            request = PromptRequest(
                prompt="user prompt",
                model_id="model",
                system_prompt="system instructions",
            )
            await provider._send_request(request)

        messages = captured_payload["json"]["messages"]  # type: ignore[index]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "system instructions"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "user prompt"

        await provider.close()


# ---------------------------------------------------------------------------
# Factory tests (get_api_key)
# ---------------------------------------------------------------------------


class TestGetApiKey:
    async def test_db_key_takes_precedence(self):
        """API key from DB should take precedence over env var."""
        with patch("src.llm.factory.get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "env-key"

            with patch("src.llm.factory.get_db_connection") as mock_db_ctx:
                mock_db = AsyncMock()
                mock_cursor = AsyncMock()
                mock_cursor.fetchone.return_value = ("db-key",)
                mock_db.execute.return_value = mock_cursor
                mock_db.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db.__aexit__ = AsyncMock(return_value=False)
                mock_db_ctx.return_value = mock_db

                result = await get_api_key(ProviderType.OPENROUTER)

        assert result == "db-key"

    async def test_env_fallback_when_no_db_key(self):
        """Falls back to env var when DB has no key."""
        with patch("src.llm.factory.get_db_connection") as mock_db_ctx:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)
            mock_db_ctx.return_value = mock_db

            with patch("src.llm.factory.get_settings") as mock_settings:
                mock_settings.return_value.openrouter_api_key = "env-key"

                result = await get_api_key(ProviderType.OPENROUTER)

        assert result == "env-key"

    async def test_returns_none_when_no_key(self):
        """Returns None when neither DB nor env has a key."""
        with patch("src.llm.factory.get_db_connection") as mock_db_ctx:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)
            mock_db_ctx.return_value = mock_db

            with patch("src.llm.factory.get_settings") as mock_settings:
                mock_settings.return_value.openrouter_api_key = None

                result = await get_api_key(ProviderType.OPENROUTER)

        assert result is None
