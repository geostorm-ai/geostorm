"""Service layer for project terms."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from src.repos.term_repo import TermRepo


class TermService:
    def __init__(self, term_repo: TermRepo) -> None:
        self._term_repo = term_repo

    async def list_terms(self, project_id: str) -> list[aiosqlite.Row]:
        """Return active terms for a project."""
        return await self._term_repo.list_terms(project_id)

    async def create_term(
        self, term_id: str, project_id: str, name: str, description: str | None, now: str,
    ) -> None:
        """Create a new term."""
        await self._term_repo.create_term(term_id, project_id, name, description, now)

    async def delete_term(self, term_id: str, project_id: str) -> int:
        """Delete a term. Returns rowcount."""
        return await self._term_repo.delete_term(term_id, project_id)
