"""Edit DSL routes.

POST /projects/{project_id}/edits
    Parse edits[], store audit rows + propagation_preview, return diff.

POST /projects/{project_id}/edits/{batch_id}/commit
    Apply edits, regenerate affected views, return updated payloads.

POST /projects/{project_id}/scenes/{scene_id}/reschedule
    Convenience wrapper: produces a patch on day_scenes.day_id + order_in_day.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import Project, PropagationPreview, User
from ..schemas_v1 import (
    CommitEditsResponse,
    PropagationPreviewResponse,
)
from ..services import edit_applicator
from ..services.propagation_engine import PropagationEngine
from ..services.views import main_schedule as _ms
from ..services.views import calendar as _cal
from ..services.views import scenes_matrix as _sm
from ..services.views import cast_dood as _dood
from ..services.views.base import invalidate_views

router = APIRouter(prefix="/projects", tags=["edits"])

_VIEW_RENDERERS = {
    "main_schedule": _ms.render,
    "calendar": _cal.render,
    "scenes_matrix": _sm.render,
    "cast_dood": _dood.render,
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class EditOp(str, enum.Enum):
    patch = "patch"
    create = "create"
    delete = "delete"


class EditItem(BaseModel):
    op: EditOp
    entity: str
    id: str | None = None
    fields: dict[str, Any] | None = None


class EditBatchRequest(BaseModel):
    scenario_id: str | None = None
    edits: list[EditItem]


class RescheduleRequest(BaseModel):
    to_day_id: str
    order_in_day: int = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_project(project_id: str, user: User, session: AsyncSession) -> Project:
    result = await session.execute(
        sa.select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _preview_response(preview: PropagationPreview) -> dict:
    diff = dict(preview.diff or {})
    diff.pop("request", None)  # don't leak internal edit request back
    return {
        "batch_id": preview.batch_id,
        "diff": diff,
        "expires_at": preview.expires_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@router.post("/{project_id}/edits", response_model=PropagationPreviewResponse)
async def preview_edits(
    project_id: str,
    body: EditBatchRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _get_project(project_id, user, session)

    # Validate entities upfront
    for item in body.edits:
        if item.entity not in edit_applicator.ALLOWED_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported entity: {item.entity!r}",
            )

    raw_edits = [e.model_dump() for e in body.edits]
    preview = await PropagationEngine.preview(
        project_id=project_id,
        user_id=user.id,
        raw_edits=raw_edits,
        session=session,
    )
    return _preview_response(preview)


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

@router.post("/{project_id}/edits/{batch_id}/commit", response_model=CommitEditsResponse)
async def commit_edits(
    project_id: str,
    batch_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    project = await _get_project(project_id, user, session)

    preview = await PropagationEngine.get_preview(batch_id, session)
    if not preview or preview.project_id != project_id:
        raise HTTPException(status_code=404, detail="Preview not found")
    if preview.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Preview is {preview.status}, cannot commit",
        )
    if preview.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Preview has expired")

    diff = preview.diff or {}
    breaks = diff.get("breaks", [])
    if breaks:
        raise HTTPException(status_code=409, detail={"message": "Hard breaks prevent commit", "breaks": breaks})

    # Apply edits to DB
    raw_edits: list[dict] = (diff.get("request") or {}).get("edits", [])
    try:
        await edit_applicator.apply(project_id, raw_edits, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Mark preview confirmed
    await session.execute(
        sa.text(
            "UPDATE propagation_previews "
            "SET status = 'confirmed', confirmed_at = NOW() "
            "WHERE batch_id = :bid"
        ),
        {"bid": batch_id},
    )

    # Mark audit rows propagated
    await session.execute(
        sa.text("UPDATE edits SET propagated = TRUE WHERE batch_id = :bid"),
        {"bid": batch_id},
    )

    # Determine scenario_id to use (default to project's live scenario)
    scenario_id: str | None = project.live_scenario_id

    # Invalidate + regenerate affected views
    affected_views: list[str] = diff.get("views_affected", [])
    await invalidate_views(project_id, affected_views, scenario_id, session)
    await session.commit()

    regenerated: dict[str, dict] = {}
    for view_name in affected_views:
        renderer = _VIEW_RENDERERS.get(view_name)
        if renderer:
            regenerated[view_name] = await renderer(project_id, scenario_id, session, use_cache=False)

    # Enqueue call-sheet regen + publish SSE events
    try:
        from arq import create_pool
        from ..worker import get_redis_settings
        from ..services import sse as _sse

        pool = await create_pool(get_redis_settings())

        if "main_schedule" in affected_views:
            shoot_day_rows = (await session.execute(
                sa.text("SELECT id FROM days WHERE project_id = :pid AND kind = 'shoot'"),
                {"pid": project_id},
            )).fetchall()
            for row in shoot_day_rows:
                await pool.enqueue_job(
                    "regenerate_call_sheet",
                    project_id, row.id, user.id, scenario_id,
                )

        # Run flag detector after every successful commit
        await pool.enqueue_job("run_flag_detector", project_id, scenario_id)

        await pool.close()

        # Determine event kinds from the diff's edit list
        edited_entities = {e.get("entity") for e in raw_edits}

        if "day_scenes" in edited_entities:
            await _sse.publish(project_id, {
                "kind": "scene_rescheduled",
                "batch_id": batch_id,
                "views_affected": affected_views,
            })
        elif edited_entities & {"days", "locations"}:
            await _sse.publish(project_id, {
                "kind": "day_updated",
                "batch_id": batch_id,
                "views_affected": affected_views,
            })
        else:
            await _sse.publish(project_id, {
                "kind": "day_updated",
                "batch_id": batch_id,
                "views_affected": affected_views,
            })
    except Exception:
        pass  # Redis unavailable — don't fail the commit

    return {"ok": True, "views_regenerated": regenerated}


# ---------------------------------------------------------------------------
# Reschedule shortcut
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/scenes/{scene_id}/reschedule",
    response_model=PropagationPreviewResponse,
)
async def reschedule_scene(
    project_id: str,
    scene_id: str,
    body: RescheduleRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _get_project(project_id, user, session)

    # Verify day belongs to the same project
    day_check = (await session.execute(
        sa.text("SELECT id FROM days WHERE id = :did AND project_id = :pid"),
        {"did": body.to_day_id, "pid": project_id},
    )).first()
    if not day_check:
        raise HTTPException(status_code=404, detail="Target day not found in project")

    # Find the day_scene link for this scene
    ds_row = (await session.execute(
        sa.text("SELECT id FROM day_scenes WHERE scene_id = :sid"),
        {"sid": scene_id},
    )).first()
    if not ds_row:
        raise HTTPException(status_code=404, detail="Scene is not scheduled on any day")

    raw_edits = [
        {
            "op": "patch",
            "entity": "day_scenes",
            "id": ds_row.id,
            "fields": {"day_id": body.to_day_id, "order_in_day": body.order_in_day},
        }
    ]
    preview = await PropagationEngine.preview(
        project_id=project_id,
        user_id=user.id,
        raw_edits=raw_edits,
        session=session,
    )
    return _preview_response(preview)
