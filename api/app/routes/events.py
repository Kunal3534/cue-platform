"""Project-level SSE event stream.

GET /projects/{project_id}/events
  Subscribes to Redis pub/sub channel `project:{id}:events`.
  Streams SSE data frames to the client until they disconnect.

Event schema defined in services/events.py.
"""
from __future__ import annotations

from typing import AsyncIterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import User
from ..services import sse as _sse

router = APIRouter(prefix="/projects", tags=["events"])


@router.get("/{project_id}/events")
async def project_events(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> StreamingResponse:
    # Verify ownership
    row = (await session.execute(
        sa.text("SELECT id FROM projects WHERE id=:pid AND owner_id=:uid"),
        {"pid": project_id, "uid": user.id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    async def generator() -> AsyncIterator[str]:
        async for raw_json in _sse.subscribe(project_id):
            yield f"data: {raw_json}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
