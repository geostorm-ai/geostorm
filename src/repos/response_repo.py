"""Repository for responses, mentions, and citations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos import GetConnection
    from src.services.mention_service import DetectedMention


class ResponseRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def list_responses_for_run(
        self, run_id: str, limit: int, offset: int,
    ) -> tuple[int, list[aiosqlite.Row]]:
        """COUNT + SELECT responses with pagination. Returns (total, rows)."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM responses WHERE run_id = ?", (run_id,),
            )
            count_row = await cursor.fetchone()
            total: int = count_row[0] if count_row else 0

            cursor = await db.execute(
                "SELECT * FROM responses WHERE run_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            )
            rows = list(await cursor.fetchall())
        return total, rows

    async def get_mentions_for_responses(self, response_ids: list[str]) -> list[aiosqlite.Row]:
        """Batch SELECT mentions for multiple response IDs (fixes N+1)."""
        if not response_ids:
            return []
        placeholders = ",".join("?" for _ in response_ids)
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"SELECT * FROM mentions WHERE response_id IN ({placeholders})",
                response_ids,
            )
            return list(await cursor.fetchall())

    async def get_non_error_responses(self, run_id: str) -> list[aiosqlite.Row]:
        """SELECT non-error responses for a run (for the analysis pipeline)."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT id, response_text FROM responses WHERE run_id = ? AND error_message IS NULL",
                (run_id,),
            )
            return list(await cursor.fetchall())

    async def store_response(  # noqa: PLR0913
        self,
        run_id: str,
        project_id: str,
        term_id: str,
        provider_name: str,
        model_name: str,
        response_text: str,
        latency_ms: int | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost_usd: float | None,
    ) -> str:
        """INSERT a success response. Returns the response_id."""
        response_id = uuid.uuid4().hex
        now_iso = datetime.now(tz=UTC).isoformat()
        async with self._get_connection() as db:
            await db.execute(
                """
                INSERT INTO responses
                    (id, run_id, project_id, term_id, provider_name, model_name,
                     response_text, latency_ms, token_count_prompt, token_count_completion,
                     cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id, run_id, project_id, term_id, provider_name, model_name,
                    response_text, latency_ms, prompt_tokens, completion_tokens,
                    cost_usd, now_iso,
                ),
            )
            await db.commit()
        return response_id

    async def store_error_response(  # noqa: PLR0913
        self,
        run_id: str,
        project_id: str,
        term_id: str,
        provider_name: str,
        model_name: str,
        error_message: str,
    ) -> str:
        """INSERT an error (dead-letter) response. Returns the response_id."""
        response_id = uuid.uuid4().hex
        now_iso = datetime.now(tz=UTC).isoformat()
        async with self._get_connection() as db:
            await db.execute(
                """
                INSERT INTO responses
                    (id, run_id, project_id, term_id, provider_name, model_name,
                     response_text, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (response_id, run_id, project_id, term_id, provider_name, model_name, "", error_message, now_iso),
            )
            await db.commit()
        return response_id

    async def store_mentions(self, response_id: str, mentions: list[DetectedMention]) -> list[str]:
        """Batch INSERT mentions for a response. Returns list of mention IDs."""
        if not mentions:
            return []

        ids: list[str] = []
        async with self._get_connection() as db:
            for mention in mentions:
                mention_id = uuid.uuid4().hex
                detected_at = datetime.now(tz=UTC).isoformat()
                await db.execute(
                    "INSERT INTO mentions"
                    " (id, response_id, mention_type, target_name, position_chars,"
                    " position_words, list_position, context_before, context_after, detected_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        mention_id,
                        response_id,
                        mention.mention_type.value,
                        mention.target_name,
                        mention.position_chars,
                        mention.position_words,
                        mention.list_position,
                        mention.context_before,
                        mention.context_after,
                        detected_at,
                    ),
                )
                ids.append(mention_id)
            await db.commit()
        return ids

    async def cleanup_old_responses(self, cutoff: str) -> int:
        """UPDATE to clear response_text for retention. Returns rowcount."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "UPDATE responses SET response_text = ''"
                " WHERE created_at < ? AND error_message IS NULL AND response_text != ''",
                (cutoff,),
            )
            cleaned = cursor.rowcount
            await db.commit()
        return cleaned
