"""LLM provider types and shared data contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ProviderType(StrEnum):
    """Supported LLM provider types."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


# ---------------------------------------------------------------------------
# Model catalog — curated models available through OpenRouter
# ---------------------------------------------------------------------------

RECOMMENDED_MODELS: list[dict[str, str]] = [
    {"id": "anthropic/claude-sonnet-4.6", "name": "Claude Sonnet 4.6"},
    {"id": "openai/gpt-5.2", "name": "GPT-5.2"},
    {"id": "google/gemini-3-flash-preview", "name": "Gemini 3 Flash"},
]


def with_web_search(model_id: str) -> str:
    """Append OpenRouter's :online suffix for web search grounding.

    Idempotent — if the model already has :online, it's returned unchanged.
    """
    if model_id.endswith(":online"):
        return model_id
    return f"{model_id}:online"


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
