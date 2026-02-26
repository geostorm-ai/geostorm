"""Thin wrapper around Pydantic AI for sending LLM prompts."""

from __future__ import annotations

import re
import time
from http import HTTPStatus
from typing import TypeVar

from genai_prices import Usage, calc_price
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from src.llm.base import LLMError, PromptRequest, PromptResponse, ProviderType
from src.llm.factory import create_model

T = TypeVar("T", bound=BaseModel)

_STATUS_CODE_RE = re.compile(r"status_code:\s*(\d{3})")

_ERROR_MAP: dict[int, tuple[str, bool]] = {
    HTTPStatus.UNAUTHORIZED: (
        "Authentication failed. Your OpenRouter API key is invalid or has been disabled. "
        "Go to Settings to enter a valid key (starts with sk-or-).",
        False,
    ),
    HTTPStatus.PAYMENT_REQUIRED: (
        "Insufficient credits. Your OpenRouter account has no remaining funds. "
        "Add credits at openrouter.ai/credits and try again.",
        False,
    ),
    HTTPStatus.FORBIDDEN: (
        "Request blocked. The AI model flagged this request as requiring moderation. "
        "Try rephrasing your monitoring terms.",
        False,
    ),
    HTTPStatus.REQUEST_TIMEOUT: (
        "Request timed out. The AI model took too long to respond. "
        "This is usually temporary — try again in a few minutes.",
        True,
    ),
    HTTPStatus.TOO_MANY_REQUESTS: (
        "Rate limited. Too many requests to OpenRouter. "
        "Wait a few minutes and try again, or check your rate limits at openrouter.ai.",
        True,
    ),
    HTTPStatus.BAD_GATEWAY: (
        "Model unavailable. The selected AI model is temporarily down. "
        "This is usually temporary — try again shortly.",
        True,
    ),
    HTTPStatus.SERVICE_UNAVAILABLE: (
        "No model provider available. No provider can currently serve this model. "
        "Try again later or switch to a different model.",
        True,
    ),
}


def _classify_llm_error(exc: Exception, provider: ProviderType) -> LLMError:
    """Inspect an LLM exception and return a user-friendly LLMError."""
    raw = str(exc)
    if provider == ProviderType.OPENROUTER:
        match = _STATUS_CODE_RE.search(raw)
        if match:
            status = int(match.group(1))
            if status in _ERROR_MAP:
                message, retryable = _ERROR_MAP[status]
                return LLMError(message, provider=provider, is_retryable=retryable)
        return LLMError(f"OpenRouter error: {raw}", provider=provider)
    return LLMError(raw, provider=provider)


async def send_prompt(request: PromptRequest, provider_type: ProviderType) -> PromptResponse:
    """Send a prompt via Pydantic AI and return a PromptResponse."""
    model = await create_model(provider_type, request.model_id)
    agent: Agent[None, str] = Agent(model, instructions=request.system_prompt or "")

    settings = _build_settings(request)

    start = time.perf_counter()
    try:
        result = await agent.run(request.prompt, model_settings=settings)
    except Exception as e:
        raise _classify_llm_error(e, provider_type) from e
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage = result.usage()
    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0

    cost_usd = 0.0
    # Strip :online suffix — genai_prices doesn't recognize OpenRouter's online variants
    pricing_model_id = request.model_id.removesuffix(":online")
    try:
        price = calc_price(
            Usage(input_tokens=input_tokens, output_tokens=output_tokens),
            model_ref=pricing_model_id,
            provider_id=provider_type.value,
        )
        if price:
            cost_usd = float(price.total_price)
    except LookupError:
        pass

    return PromptResponse(
        text=result.output,
        model_id=request.model_id,
        provider=provider_type,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


async def send_structured_prompt(
    request: PromptRequest,
    provider_type: ProviderType,
    output_type: type[T],
) -> T:
    """Send a prompt and parse the response into a Pydantic model."""
    model = await create_model(provider_type, request.model_id)
    agent: Agent[None, T] = Agent(model, output_type=output_type, instructions=request.system_prompt or "")

    settings = _build_settings(request)

    try:
        result = await agent.run(request.prompt, model_settings=settings)
    except Exception as e:
        raise _classify_llm_error(e, provider_type) from e

    return result.output


def _build_settings(request: PromptRequest) -> ModelSettings:
    """Build ModelSettings from a PromptRequest."""
    settings = ModelSettings()
    if request.temperature is not None:
        settings["temperature"] = request.temperature
    if request.max_tokens is not None:
        settings["max_tokens"] = request.max_tokens
    return settings
