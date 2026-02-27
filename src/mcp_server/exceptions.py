"""MCP-specific exceptions raised by tool helpers."""

from __future__ import annotations


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be resolved by ID or name."""

    def __init__(self, project: str, available: list[str]) -> None:
        names = ", ".join(available) or "none"
        super().__init__(f"Project '{project}' not found. Available projects: {names}")


class RunNotFoundError(Exception):
    """Raised when a run ID does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Run '{run_id}' not found")
