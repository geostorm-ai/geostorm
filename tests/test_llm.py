"""Tests for the LLM provider layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.base import (
    LLMError,
    PromptRequest,
    PromptResponse,
    ProviderType,
)
from src.llm.factory import get_api_key
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
# send_prompt / send_structured_prompt tests
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


def _mock_run_result(text: str = "test response", input_tokens: int = 10, output_tokens: int = 20) -> MagicMock:
    """Create a mock result from Agent.run()."""
    result = MagicMock()
    result.output = text
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    result.usage.return_value = usage
    return result


class TestSendPrompt:
    async def test_send_prompt_success(self):
        from src.llm.client import send_prompt

        mock_result = _mock_run_result()

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
            patch("src.llm.client.calc_price", return_value=None),
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="openai/gpt-4o")
            result = await send_prompt(request, ProviderType.OPENROUTER)

        assert result.text == "test response"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30
        assert result.provider == ProviderType.OPENROUTER

    async def test_send_prompt_with_cost(self):
        from src.llm.client import send_prompt

        mock_result = _mock_run_result()
        mock_price = MagicMock()
        mock_price.total_price = 0.005

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
            patch("src.llm.client.calc_price", return_value=mock_price),
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="openai/gpt-4o")
            result = await send_prompt(request, ProviderType.OPENROUTER)

        assert result.cost_usd == 0.005

    async def test_send_prompt_wraps_agent_error(self):
        from src.llm.client import send_prompt

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("API failed"))
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="openai/gpt-4o")

            with pytest.raises(LLMError) as exc_info:
                await send_prompt(request, ProviderType.OPENROUTER)

            assert "API failed" in str(exc_info.value)
            assert exc_info.value.provider == ProviderType.OPENROUTER

    async def test_send_prompt_passes_settings(self):
        from src.llm.client import send_prompt

        mock_result = _mock_run_result()

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
            patch("src.llm.client.calc_price", return_value=None),
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="model", temperature=0.5, max_tokens=100)
            await send_prompt(request, ProviderType.OPENROUTER)

            call_kwargs = mock_agent_instance.run.call_args
            settings = call_kwargs.kwargs["model_settings"]
            assert settings.get("temperature") == 0.5
            assert settings.get("max_tokens") == 100


class TestSendStructuredPrompt:
    async def test_send_structured_prompt_success(self):
        from pydantic import BaseModel

        from src.llm.client import send_structured_prompt

        class TestOutput(BaseModel):
            name: str
            value: int

        mock_result = MagicMock()
        mock_result.output = TestOutput(name="test", value=42)

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="model", temperature=0.3)
            result = await send_structured_prompt(request, ProviderType.OPENROUTER, TestOutput)

        assert result.name == "test"
        assert result.value == 42

    async def test_send_structured_prompt_wraps_error(self):
        from pydantic import BaseModel

        from src.llm.client import send_structured_prompt

        class TestOutput(BaseModel):
            name: str

        with (
            patch("src.llm.client.create_model", new_callable=AsyncMock) as mock_create,
            patch("src.llm.client.Agent") as mock_agent_cls,
        ):
            mock_create.return_value = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("parse failed"))
            mock_agent_cls.return_value = mock_agent_instance

            request = PromptRequest(prompt="test", model_id="model")

            with pytest.raises(LLMError):
                await send_structured_prompt(request, ProviderType.OPENROUTER, TestOutput)


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
