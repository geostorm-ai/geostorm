"""MCP server exposing GeoStorm perception data to LLM clients."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from src.container import (
    alert_service,
    project_repo,
    project_service,
    run_service,
    term_repo,
)
from src.models import AlertSeverity

mcp = FastMCP(
    "GeoStorm",
    instructions=(
        "GeoStorm monitors how AI models perceive and recommend software products. "
        "Use these tools to explore projects, perception scores, runs, alerts, and trends."
    ),
)


@mcp.tool()
async def list_projects() -> list[dict[str, Any]]:
    """List all monitored projects with their latest perception score, run count, and active alert count.

    Use this first to discover project IDs, then pass them to other tools.
    """
    projects = await project_service.list_projects()
    return [p.model_dump(mode="json") for p in projects]


@mcp.tool()
async def get_project_detail(project_id: str) -> dict[str, Any]:
    """Get full details for a project: brand info, competitors, search terms, and monitoring schedule.

    Args:
        project_id: The project ID (get this from list_projects).
    """
    row = await project_repo.get_project(project_id)
    if not row:
        return {"error": f"Project '{project_id}' not found"}
    detail = await project_service.get_project_detail(project_id, row)
    return detail.model_dump(mode="json")


@mcp.tool()
async def get_perception_scores(
    project_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Get perception score time-series for a project.

    Shows overall score, recommendation share, position average, and trend over time.

    Args:
        project_id: The project ID.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).
    """
    result = await run_service.get_perception(project_id, start_date, end_date)
    return result.model_dump(mode="json")


@mcp.tool()
async def get_perception_breakdown(project_id: str) -> dict[str, Any]:
    """Get perception breakdown by search term and by AI provider for the latest scoring period.

    Shows which terms and which AI models mention the product most.

    Args:
        project_id: The project ID.
    """
    term_rows = await term_repo.list_active_term_ids_and_names(project_id)
    term_names = {row["id"]: row["name"] for row in term_rows}
    result = await run_service.get_perception_breakdown(project_id, term_names)
    return result.model_dump(mode="json")


@mcp.tool()
async def get_recent_runs(
    project_id: str,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    """Get recent monitoring runs for a project (paginated).

    Args:
        project_id: The project ID.
        limit: Max results to return (default 20).
        offset: Pagination offset.
        status: Optional filter by run status (e.g. 'completed', 'running', 'failed').
    """
    result = await run_service.list_runs(project_id, limit, offset, status)
    return result.model_dump(mode="json")


@mcp.tool()
async def get_run_detail(run_id: str) -> dict[str, Any]:
    """Get details for a single monitoring run, including perception score and competitors detected.

    Args:
        run_id: The run ID (get this from get_recent_runs).
    """
    result = await run_service.get_run_detail(run_id)
    if not result:
        return {"error": f"Run '{run_id}' not found"}
    return result.model_dump(mode="json")


@mcp.tool()
async def get_alerts(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    severity: str | None = None,
    acknowledged: bool | None = None,
) -> list[dict[str, Any]]:
    """Get alerts and anomalies detected for a project.

    Args:
        project_id: The project ID.
        limit: Max results to return (default 50).
        offset: Pagination offset.
        severity: Optional minimum severity filter ('info', 'warning', 'critical').
        acknowledged: Optional filter by acknowledgement status.
    """
    sev = AlertSeverity(severity) if severity else None
    alerts = await alert_service.list_alerts(
        project_id, limit=limit, offset=offset, severity=sev, acknowledged=acknowledged,
    )
    return [a.model_dump(mode="json") for a in alerts]


@mcp.tool()
async def get_trajectory(
    project_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "day",
) -> dict[str, Any]:
    """Get historical trajectory data showing recommendation share, position, and competitor delta over time.

    Args:
        project_id: The project ID.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).
        period: Aggregation period — 'day', 'week', or 'month' (default 'day').
    """
    result = await run_service.get_trajectory(project_id, start_date, end_date, period)
    return result.model_dump(mode="json")
