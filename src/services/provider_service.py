"""Service layer for LLM providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos.provider_repo import ProviderRepo


class ProviderService:
    def __init__(self, provider_repo: ProviderRepo) -> None:
        self._provider_repo = provider_repo

    async def list_providers(self, project_id: str) -> list[aiosqlite.Row]:
        """Return all providers for a project."""
        return await self._provider_repo.list_providers(project_id)

    async def create_provider(
        self,
        provider_id: str,
        project_id: str,
        provider_name: str,
        model_name: str,
        now: str,
    ) -> aiosqlite.Row | None:
        """Create a provider after duplicate check. Returns existing row if duplicate."""
        existing = await self._provider_repo.find_provider(project_id, provider_name, model_name)
        if existing:
            return existing  # caller raises 409
        await self._provider_repo.create_provider(provider_id, project_id, provider_name, model_name, now)
        return None

    async def update_provider(
        self, provider_id: str, project_id: str, updates: dict[str, object],
    ) -> tuple[int, aiosqlite.Row | None]:
        """Update a provider. Returns (rowcount, refreshed row)."""
        return await self._provider_repo.update_provider(provider_id, project_id, updates)

    async def delete_provider(self, provider_id: str, project_id: str) -> int:
        """Delete a provider. Returns rowcount."""
        return await self._provider_repo.delete_provider(provider_id, project_id)
