"""Service for detecting brand and competitor mentions in LLM responses."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import logfire
from pydantic import BaseModel

from src.models import MentionType

if TYPE_CHECKING:
    from src.repos.response_repo import ResponseRepo

logger = logging.getLogger(__name__)


class ListItem(BaseModel):
    """A single item parsed from a numbered list in an LLM response."""

    position: int
    text: str
    char_offset: int


class DetectedMention(BaseModel):
    """Intermediate mention result before database storage."""

    mention_type: MentionType
    target_name: str
    position_chars: int
    position_words: int
    list_position: int | None
    context_before: str
    context_after: str


_LIST_PATTERN = re.compile(r"^\s*(?:\*\*)?(\d+)[.)]\s*(?:\*\*)?\s*(.+)", re.MULTILINE)


def parse_numbered_list(response_text: str) -> list[ListItem]:
    """Parse numbered list items from an LLM response.

    Recognises patterns like ``1. Name - desc``, ``1) Name``, and ``**1. Name**``.
    Returns items with 1-based positions and character offsets.
    """
    items: list[ListItem] = []
    for match in _LIST_PATTERN.finditer(response_text):
        position = int(match.group(1))
        text = match.group(2).strip()
        char_offset = match.start()
        items.append(ListItem(position=position, text=text, char_offset=char_offset))
    return items


def _strip_markdown(text: str) -> str:
    """Remove markdown emphasis markers (**, *, `) from text."""
    return text.replace("**", "").replace("*", "").replace("`", "")


def _count_words_before(text: str, char_position: int) -> int:
    """Count the number of whitespace-delimited words before a character position."""
    before = text[:char_position]
    return len(before.split())


def _extract_context(text: str, match_start: int, match_end: int, max_chars: int = 50) -> tuple[str, str]:
    """Extract up to *max_chars* of context before and after a match."""
    context_before_start = max(0, match_start - max_chars)
    context_before = text[context_before_start:match_start]
    context_after_end = min(len(text), match_end + max_chars)
    context_after = text[match_end:context_after_end]
    return context_before, context_after


def _find_list_position(list_items: list[ListItem], name: str) -> int | None:
    """Return the list position of *name* if it appears in a parsed numbered list."""
    pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    for item in list_items:
        cleaned = _strip_markdown(item.text)
        if pattern.search(cleaned):
            return item.position
    return None


def detect_mentions(
    response_text: str,
    brand_name: str,
    brand_aliases: list[str],
    competitors: list[str],
) -> list[DetectedMention]:
    """Detect brand and competitor mentions in a response.

    This is a pure function with no database access.  It strips markdown
    emphasis before matching, uses word-boundary regex for accuracy, and
    tracks character position, word position, numbered-list position, and
    surrounding context for every match.
    """
    if not response_text:
        return []

    cleaned_text = _strip_markdown(response_text)
    list_items = parse_numbered_list(response_text)

    brand_names = [brand_name, *brand_aliases]
    name_type_pairs: list[tuple[str, MentionType]] = [
        (name, MentionType.BRAND) for name in brand_names
    ] + [
        (name, MentionType.COMPETITOR) for name in competitors
    ]

    mentions: list[DetectedMention] = []
    for name, mention_type in name_type_pairs:
        if not name:
            continue
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(cleaned_text):
            position_chars = match.start()
            position_words = _count_words_before(cleaned_text, position_chars)
            list_position = _find_list_position(list_items, name)
            context_before, context_after = _extract_context(cleaned_text, match.start(), match.end())

            mentions.append(
                DetectedMention(
                    mention_type=mention_type,
                    target_name=name,
                    position_chars=position_chars,
                    position_words=position_words,
                    list_position=list_position,
                    context_before=context_before,
                    context_after=context_after,
                ),
            )

    return mentions


class MentionService:
    def __init__(self, response_repo: ResponseRepo) -> None:
        self._response_repo = response_repo

    async def store_mentions(self, response_id: str, mentions: list[DetectedMention]) -> list[str]:
        """Persist detected mentions to the database."""
        if not mentions:
            return []

        ids = await self._response_repo.store_mentions(response_id, mentions)
        logger.info("Stored %d mentions for response %s", len(ids), response_id)
        return ids

    async def detect_and_store_mentions_for_response(
        self,
        response_id: str,
        response_text: str,
        brand_name: str,
        brand_aliases: list[str],
        competitors: list[str],
    ) -> list[str]:
        """Detect mentions in *response_text* and persist them."""
        with logfire.span("mention detection", response_id=response_id):
            detected = detect_mentions(response_text, brand_name, brand_aliases, competitors)
            return await self.store_mentions(response_id, detected)
