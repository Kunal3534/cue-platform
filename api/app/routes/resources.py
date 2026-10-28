"""Generic CRUD for the 12 resource kinds.

All resource tables have a project_id column and are safe to expose under a
single parameterised router.  Table names are validated against a whitelist
before use in any SQL statement.

Routes:
  GET    /projects/{project_id}/resources/{kind}                    — list
  POST   /projects/{project_id}/resources/{kind}                    — create
  PATCH  /projects/{project_id}/resources/{kind}/{resource_id}      — patch
  DELETE /projects/{project_id}/resources/{kind}/{resource_id}      — delete
"""
from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import Project, User
from ..services import edit_applicator

router = APIRouter(prefix="/projects", tags=["resources"])

_RESOURCE_TABLES: frozenset[str] = frozenset({
    # original set (had limited CRUD via edit_applicator)
    "props",
    "animals",
    "picture_vehicles",
    "camera_units",
    "junior_artist_calls",
    "locations",
    # Week 6 additions
    "vfx_shots",
    "sfx_effects",
    "hmu_sessions",
    "wardrobe_looks",
    "art_builds",
    "permits",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_project(project_id: str, user: User, session: AsyncSession) -> Project:
    result = await session.execute(
        sa.select(Project).where(
            Project.id == project_id,
            sa.or_(Project.owner_id == user.id, sa.literal(is_team_member(user))),
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _validate_kind(kind: str) -> None:
    if kind not in _RESOURCE_TABLES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown resource kind {kind!r}. "
                   f"Valid kinds: {sorted(_RESOURCE_TABLES)}",
        )


def _row_to_dict(row: Any) -> dict:
    return dict(row._mapping)


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/resources/{kind}
# ---------------------------------------------------------------------------

@router.get("/{project_id}/resources/{kind}")
async def list_resources(
    project_id: str,
    kind: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[dict]:
    await _get_project(project_id, user, session)
    _validate_kind(kind)

    rows = (await session.execute(
        sa.text(f"SELECT * FROM {kind} WHERE project_id = :pid ORDER BY created_at"),
        {"pid": project_id},
    )).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/resources/{kind}
# ---------------------------------------------------------------------------

@router.post("/{project_id}/resources/{kind}", status_code=201)
async def create_resource(
    project_id: str,
    kind: str,
    body: dict[str, Any],
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _get_project(project_id, user, session)
    _validate_kind(kind)

    try:
        await edit_applicator.apply(
            project_id,
            [{"op": "create", "entity": kind, "fields": body}],
            session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH /projects/{project_id}/resources/{kind}/{resource_id}
# ---------------------------------------------------------------------------

@router.patch("/{project_id}/resources/{kind}/{resource_id}")
async def patch_resource(
    project_id: str,
    kind: str,
    resource_id: str,
    body: dict[str, Any],
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _get_project(project_id, user, session)
    _validate_kind(kind)

    # Verify the row exists and belongs to this project
    row = (await session.execute(
        sa.text(f"SELECT id FROM {kind} WHERE id = :rid AND project_id = :pid"),
        {"rid": resource_id, "pid": project_id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"{kind} {resource_id!r} not found")

    try:
        await edit_applicator.apply(
            project_id,
            [{"op": "patch", "entity": kind, "id": resource_id, "fields": body}],
            session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}/resources/{kind}/{resource_id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}/resources/{kind}/{resource_id}", status_code=204, response_class=Response, response_model=None)
async def delete_resource(
    project_id: str,
    kind: str,
    resource_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    await _get_project(project_id, user, session)
    _validate_kind(kind)

    row = (await session.execute(
        sa.text(f"SELECT id FROM {kind} WHERE id = :rid AND project_id = :pid"),
        {"rid": resource_id, "pid": project_id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"{kind} {resource_id!r} not found")

    try:
        await edit_applicator.apply(
            project_id,
            [{"op": "delete", "entity": kind, "id": resource_id}],
            session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await session.commit()
