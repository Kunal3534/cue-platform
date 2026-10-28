"""Export routes.

GET  /projects/{project_id}/exports/{view}
     Stream a single xlsx report for the given view.

POST /projects/{project_id}/exports/bundle
     Enqueue export_bundle job → returns job_id.

GET  /projects/{project_id}/exports/bundle/{job_id}
     Redirect to pre-signed S3 download URL for the zip (if ready).
"""
from __future__ import annotations

import io
import tempfile
import uuid
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, RedirectResponse

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import User
from ..schemas_v1 import ExportBundleResponse
from ..services import storage
from ..services.project_graph import ProjectGraph

router = APIRouter(prefix="/projects", tags=["exports"])

_VIEW_TO_MODULE = {
    "main_schedule": "main_schedule",
    "cast_dood":     "cast_dood",
    "scenes_matrix": "scenes_matrix",
    "calendar":      "calendar",
    "vehicles":      "vehicles",
    "cameras":       "cameras",
    "juniors":       "juniors",
    "props":         "props",
    "animals":       "animals",
    "vfx":           "vfx",
    "sfx_stunts":    "sfx_stunts",
    "hmu":           "hmu",
    "wardrobe":      "wardrobe",
    "requirements":  "requirements",
}

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _assert_project_access(project_id: str, user: User, session) -> None:
    row = (await session.execute(
        sa.text("SELECT id FROM projects WHERE id = :pid AND (owner_id = :uid OR :team = TRUE)"),
        {"pid": project_id, "uid": user.id, "team": is_team_member(user)},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")


# ---------------------------------------------------------------------------
# GET single xlsx
# ---------------------------------------------------------------------------

@router.get("/{project_id}/exports/{view}")
async def export_view_xlsx(
    project_id: str,
    view: str,
    scenario_id: str | None = Query(None),
    user: User = Depends(current_user),
    session=Depends(get_async_db),
) -> StreamingResponse:
    await _assert_project_access(project_id, user, session)

    module_name = _VIEW_TO_MODULE.get(view)
    if module_name is None:
        raise HTTPException(status_code=404, detail=f"Unknown view: {view!r}")

    import importlib
    mod = importlib.import_module(f"app.services.reports.{module_name}")

    pg = await ProjectGraph.load(project_id, scenario_id, session)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        mod.generate(pg, tmp_path)
        with open(tmp_path, "rb") as f:
            content = f.read()
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    filename = f"{view}.xlsx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=_XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# POST bundle (async job)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/exports/bundle", response_model=ExportBundleResponse)
async def export_bundle(
    project_id: str,
    scenario_id: str | None = Query(None),
    user: User = Depends(current_user),
    session=Depends(get_async_db),
) -> dict:
    await _assert_project_access(project_id, user, session)

    job_id = str(uuid.uuid4())

    from arq import create_pool
    from ..worker import get_redis_settings
    pool = await create_pool(get_redis_settings())
    job = await pool.enqueue_job("export_bundle", project_id, job_id, scenario_id)
    await pool.close()

    return {"job_id": job_id, "arq_job_id": job.job_id if job else None}


# ---------------------------------------------------------------------------
# GET bundle status / redirect
# ---------------------------------------------------------------------------

@router.get("/{project_id}/exports/bundle/{job_id}")
async def get_bundle(
    project_id: str,
    job_id: str,
    user: User = Depends(current_user),
    session=Depends(get_async_db),
) -> RedirectResponse:
    await _assert_project_access(project_id, user, session)

    zip_key = storage.key_export_zip(project_id, job_id)
    try:
        url = storage.presigned_url(zip_key, expires_seconds=3600)
    except Exception:
        raise HTTPException(status_code=404, detail="Bundle not ready yet or job_id not found")

    return RedirectResponse(url=url, status_code=302)
