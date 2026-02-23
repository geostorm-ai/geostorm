"""OpenRouter LLM provider implementation."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import NoReturn

import httpx

from src.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    PromptRequest,
    PromptResponse,
    ProviderError,
    ProviderType,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


def _build_messages(request: PromptRequest) -> list[dict[str, str]]:
    """Build the messages list from a prompt request."""
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages


def _build_payload(request: PromptRequest, messages: list[dict[str, str]]) -> dict[str, object]:
    """Build the API request payload."""
    payload: dict[str, object] = {"model": request.model_id, "messages": messages}
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    return payload


def _parse_retry_after(response: httpx.Response) -> int | None:
    """Extract retry-after header value from a 429 response."""
    if response.status_code != 429:  # noqa: PLR2004
        return None
    retry_header = response.headers.get("retry-after")
    if not retry_header:
        return None
    with contextlib.suppress(ValueError):
        return int(retry_header)
    return None


def _extract_error_message(response: httpx.Response) -> str:
    """Extract error message from an error response body."""
    fallback = f"OpenRouter API error {response.status_code}"
    try:
        error_body = response.json()
    except Exception:  # noqa: BLE001
        return fallback
    if "error" not in error_body:
        return fallback
    error_detail = error_body["error"]
    if isinstance(error_detail, dict):
        return str(error_detail.get("message", fallback))
    return str(error_detail)


def _parse_response_text(data: dict[str, object]) -> str:
    """Extract response text from the API response data."""
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        _raise_provider_error("empty_response", "No choices in OpenRouter response")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        _raise_provider_error("invalid_response", "Invalid choice format in OpenRouter response")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        _raise_provider_error("invalid_response", "Invalid message format in OpenRouter response")
    return str(message.get("content", ""))


def _parse_usage(data: dict[str, object]) -> tuple[int, int, float]:
    """Extract token usage and cost from the API response data."""
    usage = data.get("usage")
    if isinstance(usage, dict):
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cost = float(usage.get("total_cost", 0.0))
        return prompt_tokens, completion_tokens, cost
    return 0, 0, 0.0


def _raise_provider_error(code: str, message: str) -> NoReturn:
    """Raise a non-retryable LLMProviderError."""
    raise LLMProviderError(
        ProviderError(
            code=code,
            message=message,
            provider=ProviderType.OPENROUTER,
            is_retryable=False,
        ),
    )


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API provider (OpenAI-compatible)."""

    provider_type = ProviderType.OPENROUTER

    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://geostorm.io",
                "X-Title": "GeoStorm",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def _send_request(self, request: PromptRequest) -> PromptResponse:
        """Send a chat completion request to OpenRouter."""
        messages = _build_messages(request)
        payload = _build_payload(request, messages)

        start = time.perf_counter()
        response = await self._do_post(payload)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code != 200:  # noqa: PLR2004
            self._raise_http_error(response)

        data: dict[str, object] = response.json()
        text = _parse_response_text(data)
        prompt_tokens, completion_tokens, cost_usd = _parse_usage(data)

        return PromptResponse(
            text=text,
            model_id=request.model_id,
            provider=ProviderType.OPENROUTER,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )

    async def _do_post(self, payload: dict[str, object]) -> httpx.Response:
        """Execute the HTTP POST, converting transport errors to LLMProviderError."""
        try:
            return await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                ProviderError(
                    code="timeout",
                    message=f"Request timed out: {e}",
                    provider=ProviderType.OPENROUTER,
                    is_retryable=True,
                ),
            ) from e
        except httpx.HTTPError as e:
            raise LLMProviderError(
                ProviderError(
                    code="connection_error",
                    message=f"Connection error: {e}",
                    provider=ProviderType.OPENROUTER,
                    is_retryable=True,
                ),
            ) from e

    @staticmethod
    def _raise_http_error(response: httpx.Response) -> None:
        """Raise LLMProviderError for non-200 HTTP responses."""
        raise LLMProviderError(
            ProviderError(
                code=f"http_{response.status_code}",
                message=_extract_error_message(response),
                provider=ProviderType.OPENROUTER,
                is_retryable=response.status_code in _RETRYABLE_STATUS_CODES,
                retry_after_seconds=_parse_retry_after(response),
            ),
        )

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()
