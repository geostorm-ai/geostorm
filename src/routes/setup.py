"""Setup and settings endpoints for GeoStorm API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import logfire
from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError

from src.config import get_settings
from src.database import get_db_connection
from src.llm.base import LLMProviderError, PromptRequest, ProviderType
from src.llm.factory import get_api_key
from src.llm.openrouter import OpenRouterProvider
from src.schemas import (
    ApiKeyStatusResponse,
    AutofillLLMResponse,
    AutofillRequest,
    AutofillResponse,
    SetupStatusResponse,
    StoreApiKeyRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/setup/status")
async def get_setup_status() -> SetupStatusResponse:
    has_api_key = False

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'openrouter_api_key'",
        )
        row = await cursor.fetchone()
        if row and row["value"]:
            has_api_key = True

    if not has_api_key:
        settings = get_settings()
        if settings.openrouter_api_key:
            has_api_key = True

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM projects WHERE is_demo = 0",
        )
        count_row = await cursor.fetchone()
        project_count: int = count_row["count"] if count_row else 0

    return SetupStatusResponse(
        has_api_key=has_api_key,
        has_projects=project_count > 0,
        project_count=project_count,
    )


@router.get("/settings/api-key-status")
async def get_api_key_status() -> ApiKeyStatusResponse:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'openrouter_api_key'",
        )
        row = await cursor.fetchone()
        if row and row["value"]:
            return ApiKeyStatusResponse(configured=True, source="database")

    settings = get_settings()
    if settings.openrouter_api_key:
        return ApiKeyStatusResponse(configured=True, source="environment")

    return ApiKeyStatusResponse(configured=False, source=None)


@router.post("/settings/api-key")
async def store_api_key(req: StoreApiKeyRequest) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat()

    async with get_db_connection() as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('openrouter_api_key', ?, ?)",
            (req.key, now),
        )
        await db.commit()

    return {"status": "stored"}


@router.delete("/settings/api-key")
async def delete_api_key() -> Response:
    async with get_db_connection() as db:
        await db.execute("DELETE FROM settings WHERE key = 'openrouter_api_key'")
        await db.commit()

    return Response(status_code=204)


_AUTOFILL_SYSTEM_PROMPT = """\
You are an assistant for GeoStorm, a platform that tracks how AI models \
recommend software products. GeoStorm monitors AI perception by sending \
prompts like "What are the best options for {term}?" to multiple LLM providers \
and analyzing which products get recommended.

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

_AUTOFILL_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "autofill_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string"},
                "brand_aliases": {"type": "array", "items": {"type": "string"}},
                "description": {"type": "string"},
                "competitors": {"type": "array", "items": {"type": "string"}},
                "monitoring_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "brand_name",
                "brand_aliases",
                "description",
                "competitors",
                "monitoring_terms",
            ],
            "additionalProperties": False,
        },
    },
}


@router.post("/setup/autofill")
async def autofill_project(req: AutofillRequest) -> AutofillResponse:
    api_key = await get_api_key(ProviderType.OPENROUTER)
    if not api_key:
        raise HTTPException(status_code=400, detail="No OpenRouter API key configured")

    with logfire.span('autofill project', input=req.input):
        provider = OpenRouterProvider(api_key)
        try:
            response = await provider.send_prompt(
                PromptRequest(
                    prompt=req.input,
                    model_id="google/gemini-2.0-flash-001",
                    system_prompt=_AUTOFILL_SYSTEM_PROMPT,
                    temperature=0.3,
                    response_format=_AUTOFILL_RESPONSE_FORMAT,
                ),
            )
        except LLMProviderError as e:
            logger.warning("Autofill LLM error: %s", e)
            raise HTTPException(status_code=502, detail="AI service error") from e
        finally:
            await provider.close()

        try:
            data = AutofillLLMResponse.model_validate_json(response.text)
        except ValidationError as e:
            logger.warning("Autofill returned invalid JSON: %s", response.text[:200])
            raise HTTPException(status_code=502, detail="AI returned invalid response") from e

    return AutofillResponse(
        brand_name=data.brand_name,
        brand_aliases=data.brand_aliases,
        description=data.description,
        competitors=data.competitors,
        monitoring_terms=data.monitoring_terms,
    )
