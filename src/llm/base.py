"""LLM provider base classes and shared types."""

import abc
import asyncio
import logging
from enum import StrEnum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderType(StrEnum):
    """Supported LLM provider types."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class PromptRequest(BaseModel):
    """Input for an LLM prompt request."""

    prompt: str
    model_id: str
    max_tokens: int | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    system_prompt: str | None = None


class PromptResponse(BaseModel):
    """Output from an LLM prompt request."""

    text: str
    model_id: str
    provider: ProviderType
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    latency_ms: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)


class ProviderError(BaseModel):
    """Error details from a failed LLM request."""

    code: str
    message: str
    provider: ProviderType
    is_retryable: bool
    retry_after_seconds: int | None = None


class LLMProviderError(Exception):
    """Exception wrapping a ProviderError."""

    def __init__(self, error: ProviderError) -> None:
        self.error = error
        super().__init__(error.message)


class BaseLLMProvider(abc.ABC):
    """Abstract base class for LLM providers."""

    provider_type: ProviderType

    async def send_prompt(self, request: PromptRequest) -> PromptResponse:
        """Send a prompt with retry logic (3 attempts, exponential backoff)."""
        max_retries = 3
        backoff_seconds = [1.0, 2.0, 4.0]

        last_error: LLMProviderError | None = None
        for attempt in range(max_retries):
            try:
                return await self._send_request(request)
            except LLMProviderError as e:
                last_error = e
                if not e.error.is_retryable:
                    raise
                if attempt < max_retries - 1:
                    wait_time = backoff_seconds[attempt]
                    if e.error.retry_after_seconds is not None:
                        wait_time = float(e.error.retry_after_seconds)
                    logger.warning(
                        "Retryable error from %s (attempt %d/%d), waiting %.1fs: %s",
                        self.provider_type,
                        attempt + 1,
                        max_retries,
                        wait_time,
                        e.error.message,
                    )
                    await asyncio.sleep(wait_time)

        assert last_error is not None
        raise last_error

    @abc.abstractmethod
    async def _send_request(self, request: PromptRequest) -> PromptResponse:
        """Provider-specific implementation. Subclasses must implement this."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Clean up resources (e.g., httpx client)."""
