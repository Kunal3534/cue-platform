"""Public share-link routes.

POST /projects/{project_id}/share
     Mint (or return the existing) share token for a project. Auth required.

GET  /share/{token}
     Public, read-only: project header + the live calendar payload. No auth —
     the unguessable token is the credential. Nothing here can mutate state.
"""
from __future__ import annotations

import json
import secrets

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import User
from ..services.views import calendar as _cal

router = APIRouter(tags=["share"])


@router.post("/projects/{project_id}/share")
async def mint_share_link(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    row = (await session.execute(
        sa.text("SELECT settings FROM projects WHERE id = :pid AND (owner_id = :uid OR :team = TRUE)"),
        {"pid": project_id, "uid": user.id, "team": is_team_member(user)},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    token = (row.settings or {}).get("share_token")
    if not token:
        token = secrets.token_urlsafe(16)
        await session.execute(
            sa.text(
                "UPDATE projects SET settings = settings || CAST(:patch AS jsonb) "
                "WHERE id = :pid"
            ),
            {"patch": json.dumps({"share_token": token}), "pid": project_id},
        )
        await session.commit()

    return {"token": token, "path": f"/share/{token}"}


@router.get("/share/{token}")
async def get_shared_calendar(
    token: str,
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    row = (await session.execute(
        sa.text(
            "SELECT id, title, \"window\", start_date, end_date, settings, live_scenario_id "
            "FROM projects WHERE settings->>'share_token' = :tok"
        ),
        {"tok": token},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Share link not found")

    mode = (row.settings or {}).get("mode", "film")
    calendar = await _cal.render(row.id, row.live_scenario_id, session, use_cache=True)
    payload = {
        "title": row.title,
        "window": row.window,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "mode": mode,
        "calendar": calendar,
    }
    if mode == "editorial":
        from .editorial import build_schedule
        payload["schedule"] = await build_schedule(row.id, session)
    return payload


@router.get("/share/{token}/moodboard/{date}")
async def get_shared_moodboard(
    token: str,
    date: str,
    session: AsyncSession = Depends(get_async_db),
):
    """View-only moodboard access for share-link holders."""
    from datetime import date as date_cls

    from .editorial import _serve_moodboard

    try:
        day_date = date_cls.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Bad date")

    row = (await session.execute(
        sa.text(
            "SELECT d.moodboard FROM days d "
            "JOIN projects p ON p.id = d.project_id "
            "WHERE p.settings->>'share_token' = :tok AND d.date = :dt"
        ),
        {"tok": token, "dt": day_date},
    )).first()
    return _serve_moodboard(row.moodboard if row else None)


@router.get("/share/{token}/moodboard/{date}/pages/{page}")
async def get_shared_moodboard_page(
    token: str,
    date: str,
    page: int,
    session: AsyncSession = Depends(get_async_db),
):
    from datetime import date as date_cls

    from .editorial import serve_moodboard_page

    try:
        day_date = date_cls.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Bad date")

    row = (await session.execute(
        sa.text(
            "SELECT d.project_id, d.moodboard FROM days d "
            "JOIN projects p ON p.id = d.project_id "
            "WHERE p.settings->>'share_token' = :tok AND d.date = :dt"
        ),
        {"tok": token, "dt": day_date},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Moodboard page not found")
    return serve_moodboard_page(row.project_id, day_date.isoformat(), page, row.moodboard)
