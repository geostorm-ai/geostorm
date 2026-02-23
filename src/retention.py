"""Data retention cleanup for GeoStorm."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from src.database import get_db_connection

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 30


async def cleanup_old_responses(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Clear response_text from responses older than retention_days.

    The response rows are kept (not deleted) so that linked mentions and
    citations are preserved indefinitely.  Only the large response_text
    column is nulled out to reclaim storage.

    Returns the number of cleaned rows.
    """
    cutoff = (datetime.now(tz=UTC) - timedelta(days=retention_days)).isoformat()
    cleaned = 0

    try:
        async with get_db_connection() as db:
            cursor = await db.execute(
                "UPDATE responses SET response_text = ''"
                " WHERE created_at < ? AND error_message IS NULL AND response_text != ''",
                (cutoff,),
            )
            cleaned = cursor.rowcount
            await db.commit()
    except Exception:
        logger.exception("Failed to clean up old responses")
        return 0

    if cleaned > 0:
        logger.info("Retention cleanup: cleared %d responses older than %d days", cleaned, retention_days)

    return cleaned
