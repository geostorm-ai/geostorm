"""Fuzzy project resolution: ID, name, substring, or difflib match."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from src.container import project_repo, project_service
from src.mcp_server.exceptions import ProjectNotFoundError

if TYPE_CHECKING:
    import aiosqlite

_FUZZY_MATCH_THRESHOLD = 0.6


async def resolve_project(project: str) -> tuple[str, aiosqlite.Row]:
    """Resolve a project ID or fuzzy name to (project_id, row).

    Matching precedence:
        1. Exact ID
        2. Case-insensitive exact name
        3. Substring of name
        4. difflib fuzzy match (threshold 0.6)

    Raises ProjectNotFoundError if no match is found.
    """
    # 1. Exact ID match
    row = await project_repo.get_project(project)
    if row:
        return (project, row)

    # 2. Fuzzy name matching against all projects
    all_projects = await project_service.list_projects()
    names: dict[str, str] = {p.id: p.name for p in all_projects}

    # Case-insensitive exact name match
    lower = project.lower()
    for pid, name in names.items():
        if name.lower() == lower:
            matched_row = await project_repo.get_project(pid)
            if matched_row:
                return (pid, matched_row)

    # Substring match
    for pid, name in names.items():
        if lower in name.lower():
            matched_row = await project_repo.get_project(pid)
            if matched_row:
                return (pid, matched_row)

    # difflib fuzzy match
    best_score = 0.0
    best_pid: str | None = None
    for pid, name in names.items():
        score = difflib.SequenceMatcher(None, lower, name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_pid = pid

    if best_pid and best_score >= _FUZZY_MATCH_THRESHOLD:
        matched_row = await project_repo.get_project(best_pid)
        if matched_row:
            return (best_pid, matched_row)

    raise ProjectNotFoundError(project, list(names.values()))
