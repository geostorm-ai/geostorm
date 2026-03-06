"""Term endpoints for GeoStorm API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response

from src.container import term_service
from src.routes.deps import get_project_or_404, get_writable_project_or_403
from src.schemas import CreateTermRequest, TermResponse

router = APIRouter(prefix="/api", tags=["Terms"])


@router.get("/projects/{project_id}/terms", operation_id="listTerms")
async def get_terms(project_id: str) -> list[TermResponse]:
    await get_project_or_404(project_id)
    rows = await term_service.list_terms(project_id)
    return [
        TermResponse(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("/projects/{project_id}/terms", status_code=201, operation_id="createTerm")
async def create_term(project_id: str, body: CreateTermRequest) -> TermResponse:
    await get_writable_project_or_403(project_id)
    term_id = uuid.uuid4().hex
    now = datetime.now(tz=UTC).isoformat()
    await term_service.create_term(term_id, project_id, body.name, body.description, now)
    return TermResponse(
        id=term_id,
        project_id=project_id,
        name=body.name,
        description=body.description,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@router.delete("/projects/{project_id}/terms/{term_id}", operation_id="deleteTerm")
async def delete_term(project_id: str, term_id: str) -> Response:
    await get_writable_project_or_403(project_id)
    rowcount = await term_service.delete_term(term_id, project_id)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Term not found")
    return Response(status_code=204)
