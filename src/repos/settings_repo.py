"""Repository for the settings key-value store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.repos import GetConnection


class SettingsRepo:
    def __init__(self, get_connection: GetConnection) -> None:
        self._get_connection = get_connection

    async def get_setting(self, key: str) -> str | None:
        """Return the value for *key*, or ``None`` if not set."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
        if row and row["value"]:
            return str(row["value"])
        return None

    async def upsert_setting(self, key: str, value: str, now: str) -> None:
        """Insert or replace a setting."""
        async with self._get_connection() as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
            await db.commit()

    async def delete_setting(self, key: str) -> None:
        """Delete a setting by key."""
        async with self._get_connection() as db:
            await db.execute("DELETE FROM settings WHERE key = ?", (key,))
            await db.commit()

    async def get_configured_keys(self, keys: list[str]) -> set[str]:
        """Return the subset of *keys* that have non-empty values in the settings table."""
        if not keys:
            return set()
        placeholders = ", ".join("?" for _ in keys)
        async with self._get_connection() as db:
            cursor = await db.execute(
                f"SELECT key FROM settings WHERE key IN ({placeholders}) AND value IS NOT NULL AND value != ''",
                keys,
            )
            return {row[0] for row in await cursor.fetchall()}
