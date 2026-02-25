"""LLM provider types and shared data contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field


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


class LLMError(Exception):
    """Error from an LLM request."""

    def __init__(self, message: str, *, provider: ProviderType, is_retryable: bool = False) -> None:
        self.provider = provider
        self.is_retryable = is_retryable
        super().__init__(message)
