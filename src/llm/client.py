"""Thin wrapper around Pydantic AI for sending LLM prompts."""

from __future__ import annotations

import time
from typing import TypeVar

from genai_prices import Usage, calc_price
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from src.llm.base import LLMError, PromptRequest, PromptResponse, ProviderType
from src.llm.factory import create_model

T = TypeVar("T", bound=BaseModel)


async def send_prompt(request: PromptRequest, provider_type: ProviderType) -> PromptResponse:
    """Send a prompt via Pydantic AI and return a PromptResponse."""
    model = await create_model(provider_type, request.model_id)
    agent: Agent[None, str] = Agent(model, instructions=request.system_prompt or "")

    settings = _build_settings(request)

    start = time.perf_counter()
    try:
        result = await agent.run(request.prompt, model_settings=settings)
    except Exception as e:
        raise LLMError(str(e), provider=provider_type) from e
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
        raise LLMError(str(e), provider=provider_type) from e

    return result.output


def _build_settings(request: PromptRequest) -> ModelSettings:
    """Build ModelSettings from a PromptRequest."""
    settings = ModelSettings()
    if request.temperature is not None:
        settings["temperature"] = request.temperature
    if request.max_tokens is not None:
        settings["max_tokens"] = request.max_tokens
    return settings
