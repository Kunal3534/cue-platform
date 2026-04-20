"""GET view endpoints — serve cached or freshly rendered view payloads.

GET /projects/{project_id}/views/main_schedule[?scenario_id=]
GET /projects/{project_id}/views/calendar[?scenario_id=]
GET /projects/{project_id}/views/scenes_matrix[?scenario_id=]
GET /projects/{project_id}/views/cast_dood[?scenario_id=]
"""
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import User
from ..schemas_v1 import (
    CalendarResponse,
    CastDoodResponse,
    MainScheduleResponse,
    ScenesMatrixResponse,
)
from ..services.views import main_schedule as _ms
from ..services.views import calendar as _cal
from ..services.views import scenes_matrix as _sm
from ..services.views import cast_dood as _dood

router = APIRouter(prefix="/projects", tags=["views"])

_RENDERERS = {
    "main_schedule": _ms.render,
    "calendar":      _cal.render,
    "scenes_matrix": _sm.render,
    "cast_dood":     _dood.render,
}

_RESPONSE_MODELS = {
    "main_schedule": MainScheduleResponse,
    "calendar":      CalendarResponse,
    "scenes_matrix": ScenesMatrixResponse,
    "cast_dood":     CastDoodResponse,
}


async def _resolve_scenario(
    project_id: str,
    scenario_id: str | None,
    user: User,
    session: AsyncSession,
) -> str | None:
    row = (await session.execute(
        sa.text("SELECT live_scenario_id, owner_id FROM projects WHERE id = :pid"),
        {"pid": project_id},
    )).first()
    if not row or row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return scenario_id or row.live_scenario_id


def _make_view_route(view_name: str):
    async def _handler(
        project_id: str,
        scenario_id: str | None = None,
        user: User = Depends(current_user),
        session: AsyncSession = Depends(get_async_db),
    ) -> dict:
        sid = await _resolve_scenario(project_id, scenario_id, user, session)
        renderer = _RENDERERS[view_name]
        return await renderer(project_id, sid, session, use_cache=True)

    _handler.__name__ = f"get_{view_name}"
    return _handler


for _name in _RENDERERS:
    router.add_api_route(
        f"/{{project_id}}/views/{_name}",
        _make_view_route(_name),
        methods=["GET"],
        summary=f"GET {_name} view",
        response_model=_RESPONSE_MODELS[_name],
    )
