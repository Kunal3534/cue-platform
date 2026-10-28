"""Scenarios routes — fork, diff, merge, delete.

GET    /projects/{project_id}/scenarios                     — list
POST   /projects/{project_id}/scenarios                     — fork from live
GET    /projects/{project_id}/scenarios/{scenario_id}/diff  — snapshot vs live
POST   /projects/{project_id}/scenarios/{scenario_id}/merge — create merge preview
DELETE /projects/{project_id}/scenarios/{scenario_id}       — discard
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import Project, Scenario, User
from ..services.propagation_engine import PropagationEngine

router = APIRouter(prefix="/projects", tags=["scenarios"])


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


async def _get_scenario(scenario_id: str, project_id: str, session: AsyncSession) -> Scenario:
    result = await session.execute(
        sa.select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.project_id == project_id,
            Scenario.discarded_at.is_(None),
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


async def _capture_snapshot(project_id: str, session: AsyncSession) -> dict[str, Any]:
    """Capture a lightweight schedule snapshot for scenario forking."""
    day_scene_rows = (await session.execute(
        sa.text(
            "SELECT ds.id, ds.scene_id, ds.day_id, ds.order_in_day "
            "FROM day_scenes ds "
            "JOIN days d ON ds.day_id = d.id "
            "WHERE d.project_id = :pid"
        ),
        {"pid": project_id},
    )).fetchall()

    day_rows = (await session.execute(
        sa.text(
            "SELECT id, date, kind, location_id, "
            "shoot_day_number, shift_start "
            "FROM days WHERE project_id = :pid"
        ),
        {"pid": project_id},
    )).fetchall()

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "day_scenes": [
            {
                "id": r.id,
                "scene_id": r.scene_id,
                "day_id": r.day_id,
                "order_in_day": r.order_in_day,
            }
            for r in day_scene_rows
        ],
        "days": [
            {
                "id": r.id,
                "date": r.date.isoformat() if r.date else None,
                "kind": r.kind,
                "location_id": r.location_id,
                "shoot_day_number": r.shoot_day_number,
                "shift_start": r.shift_start.isoformat() if r.shift_start else None,
            }
            for r in day_rows
        ],
    }


def _scenario_out(s: Scenario) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "name": s.name,
        "is_live": s.is_live,
        "parent_scenario_id": s.parent_scenario_id,
        "created_at": s.created_at.isoformat(),
        "merged_at": s.merged_at.isoformat() if s.merged_at else None,
        "discarded_at": s.discarded_at.isoformat() if s.discarded_at else None,
        "notes": s.notes,
    }


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ForkRequest(BaseModel):
    name: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/scenarios
# ---------------------------------------------------------------------------

@router.get("/{project_id}/scenarios")
async def list_scenarios(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[dict]:
    await _get_project(project_id, user, session)
    rows = (await session.execute(
        sa.select(Scenario)
        .where(Scenario.project_id == project_id, Scenario.discarded_at.is_(None))
        .order_by(Scenario.created_at.asc())
    )).scalars().all()
    return [_scenario_out(s) for s in rows]


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/scenarios — fork
# ---------------------------------------------------------------------------

@router.post("/{project_id}/scenarios", status_code=201)
async def fork_scenario(
    project_id: str,
    body: ForkRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    project = await _get_project(project_id, user, session)

    snapshot = await _capture_snapshot(project_id, session)

    scenario = Scenario(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=body.name,
        parent_scenario_id=project.live_scenario_id,
        is_live=False,
        created_by=user.id,
        snapshot=snapshot,
        notes=body.notes,
    )
    session.add(scenario)
    await session.commit()
    await session.refresh(scenario)
    return _scenario_out(scenario)


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/scenarios/{scenario_id}/diff
# ---------------------------------------------------------------------------

@router.get("/{project_id}/scenarios/{scenario_id}/diff")
async def get_scenario_diff(
    project_id: str,
    scenario_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _get_project(project_id, user, session)
    scenario = await _get_scenario(scenario_id, project_id, session)

    if not scenario.snapshot:
        return {"changes": [], "message": "No snapshot captured for this scenario"}

    snap_ds = {r["id"]: r for r in scenario.snapshot.get("day_scenes", [])}

    current_rows = (await session.execute(
        sa.text(
            "SELECT ds.id, ds.scene_id, ds.day_id, ds.order_in_day, "
            "       s.scene_number "
            "FROM day_scenes ds "
            "JOIN days d ON ds.day_id = d.id "
            "JOIN scenes s ON ds.scene_id = s.id "
            "WHERE d.project_id = :pid"
        ),
        {"pid": project_id},
    )).fetchall()
    current_ds = {r.id: r for r in current_rows}

    changes: list[dict] = []

    for ds_id, snap in snap_ds.items():
        if ds_id in current_ds:
            cur = current_ds[ds_id]
            if snap["day_id"] != cur.day_id or snap["order_in_day"] != cur.order_in_day:
                changes.append({
                    "type": "moved",
                    "day_scene_id": ds_id,
                    "scene_number": cur.scene_number,
                    "from_day_id": snap["day_id"],
                    "to_day_id": cur.day_id,
                    "from_order": snap["order_in_day"],
                    "to_order": cur.order_in_day,
                })
        else:
            changes.append({
                "type": "removed",
                "day_scene_id": ds_id,
                "scene_id": snap["scene_id"],
            })

    for ds_id in current_ds:
        if ds_id not in snap_ds:
            cur = current_ds[ds_id]
            changes.append({
                "type": "added",
                "day_scene_id": ds_id,
                "scene_number": cur.scene_number,
                "day_id": cur.day_id,
                "order_in_day": cur.order_in_day,
            })

    return {
        "scenario_id": scenario_id,
        "snapshot_captured_at": scenario.snapshot.get("captured_at"),
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/scenarios/{scenario_id}/merge
# ---------------------------------------------------------------------------

@router.post("/{project_id}/scenarios/{scenario_id}/merge")
async def merge_scenario(
    project_id: str,
    scenario_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    """Generate a commit preview that restores the scenario's snapshot to live.

    Returns a standard preview (batch_id + diff).  The client confirms via
    POST /projects/:id/edits/:batch_id/commit as usual, so propagation applies.
    """
    project = await _get_project(project_id, user, session)
    scenario = await _get_scenario(scenario_id, project_id, session)

    if scenario.is_live:
        raise HTTPException(status_code=409, detail="Cannot merge the live scenario into itself")
    if scenario.merged_at:
        raise HTTPException(status_code=409, detail="Scenario already merged")
    if not scenario.snapshot:
        raise HTTPException(status_code=422, detail="Scenario has no snapshot to merge from")

    snap_ds_list: list[dict] = scenario.snapshot.get("day_scenes", [])

    current_rows = (await session.execute(
        sa.text(
            "SELECT ds.id, ds.day_id, ds.order_in_day "
            "FROM day_scenes ds "
            "JOIN days d ON ds.day_id = d.id "
            "WHERE d.project_id = :pid"
        ),
        {"pid": project_id},
    )).fetchall()
    current_map = {r.id: r for r in current_rows}

    edits: list[dict] = []
    for snap in snap_ds_list:
        ds_id = snap["id"]
        if ds_id not in current_map:
            continue  # row deleted since fork — skip
        cur = current_map[ds_id]
        if snap["day_id"] != cur.day_id or snap["order_in_day"] != cur.order_in_day:
            edits.append({
                "op": "patch",
                "entity": "day_scenes",
                "id": ds_id,
                "fields": {
                    "day_id": snap["day_id"],
                    "order_in_day": snap["order_in_day"],
                },
            })

    if not edits:
        # Nothing diverged — mark merged immediately
        await session.execute(
            sa.text("UPDATE scenarios SET merged_at = NOW() WHERE id = :sid"),
            {"sid": scenario_id},
        )
        await session.commit()
        return {"ok": True, "merged": True, "batch_id": None, "edits_count": 0}

    preview = await PropagationEngine.preview(
        project_id=project_id,
        user_id=user.id,
        raw_edits=edits,
        session=session,
    )

    # Mark as merged; commit will finalise the edits
    await session.execute(
        sa.text("UPDATE scenarios SET merged_at = NOW() WHERE id = :sid"),
        {"sid": scenario_id},
    )
    await session.commit()

    diff = dict(preview.diff or {})
    diff.pop("request", None)
    return {
        "batch_id": preview.batch_id,
        "diff": diff,
        "expires_at": preview.expires_at.isoformat(),
        "edits_count": len(edits),
    }


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}/scenarios/{scenario_id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}/scenarios/{scenario_id}", status_code=204, response_class=Response, response_model=None)
async def delete_scenario(
    project_id: str,
    scenario_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    await _get_project(project_id, user, session)
    scenario = await _get_scenario(scenario_id, project_id, session)

    if scenario.is_live:
        raise HTTPException(status_code=409, detail="Cannot delete the live scenario")

    await session.execute(
        sa.text("UPDATE scenarios SET discarded_at = NOW() WHERE id = :sid"),
        {"sid": scenario_id},
    )
    await session.commit()
