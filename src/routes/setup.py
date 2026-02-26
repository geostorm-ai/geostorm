"""Setup and settings endpoints for GeoStorm API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import logfire
from fastapi import APIRouter, HTTPException, Response

from src.container import settings_service
from src.llm.base import RECOMMENDED_MODELS, LLMError, PromptRequest, ProviderType, with_web_search
from src.llm.client import send_structured_prompt
from src.llm.factory import get_api_key
from src.schemas import (
    ApiKeyStatusResponse,
    AutofillLLMResponse,
    AutofillRequest,
    AutofillResponse,
    SetupStatusResponse,
    StoreApiKeyRequest,
)
from src.services.settings_service import InvalidApiKeyError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/setup/status")
async def get_setup_status() -> SetupStatusResponse:
    return await settings_service.get_setup_status()


@router.get("/settings/api-key-status")
async def get_api_key_status() -> ApiKeyStatusResponse:
    return await settings_service.get_api_key_status()


@router.post("/settings/api-key")
async def store_api_key(req: StoreApiKeyRequest) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat()
    try:
        await settings_service.store_api_key(req.key, now)
    except InvalidApiKeyError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"status": "stored"}


@router.delete("/settings/api-key")
async def delete_api_key() -> Response:
    await settings_service.delete_api_key()
    return Response(status_code=204)


@router.get("/settings/models")
async def get_recommended_models() -> list[dict[str, str]]:
    """Return the curated list of models available through OpenRouter."""
    return RECOMMENDED_MODELS


_AUTOFILL_SYSTEM_PROMPT = """\
You are an assistant for GeoStorm, a platform that tracks how AI models \
recommend software products. GeoStorm monitors AI perception by sending \
prompts like "What are the best options for {term}?" to multiple LLM providers \
and analyzing which products get recommended.

Use web search to verify real product information — official names, actual \
competitors, what the product really does. Don't guess.

Given a company name, URL, GitHub repo, or package name, return a JSON object with:
- brand_name: the official brand/product name
- brand_aliases: list of common alternative names, abbreviations, or misspellings
- description: a one-sentence description of what this brand/product does
- competitors: list of 3-5 direct competitor names
- monitoring_terms: list of 5-8 SHORT noun phrases for monitoring AI recommendations

CRITICAL: monitoring_terms must be short phrases that complete the template \
"What are the best options for {term}?" naturally. They should surface how AI \
models perceive and recommend this product.

GOOD monitoring_terms examples (for Supabase):
- "Firebase alternative"
- "open source BaaS"
- "Supabase vs Firebase"
- "backend for React app"
- "serverless database platform"
- "real-time database service"

BAD monitoring_terms (NEVER generate these patterns):
- "Supabase status" (status query)
- "Is Supabase down?" (full question)
- "How to use Supabase" (tutorial/how-to)
- "Supabase pricing" (pricing query)
- "best Supabase alternatives" (starts with "best")
- "Supabase tutorial" (tutorial query)

Include a mix of: category phrases ("open source BaaS"), comparison phrases \
("Supabase vs Firebase"), and use-case phrases ("backend for React app").\
"""


@router.post("/setup/autofill")
async def autofill_project(req: AutofillRequest) -> AutofillResponse:
    api_key = await get_api_key(ProviderType.OPENROUTER)
    if not api_key:
        raise HTTPException(status_code=400, detail="No OpenRouter API key configured")

    with logfire.span("autofill project", input=req.input):
        try:
            data = await send_structured_prompt(
                PromptRequest(
                    prompt=req.input,
                    model_id=with_web_search("google/gemini-3-flash-preview"),
                    system_prompt=_AUTOFILL_SYSTEM_PROMPT,
                    temperature=0.3,
                ),
                provider_type=ProviderType.OPENROUTER,
                output_type=AutofillLLMResponse,
            )
        except LLMError as e:
            logger.warning("Autofill LLM error: %s", e)
            raise HTTPException(status_code=502, detail=str(e)) from e
        except Exception as e:
            logger.warning("Autofill error: %s", e)
            raise HTTPException(status_code=502, detail="AI returned invalid response") from e

    return AutofillResponse(
        brand_name=data.brand_name,
        brand_aliases=data.brand_aliases,
        description=data.description,
        competitors=data.competitors,
        monitoring_terms=data.monitoring_terms,
    )
