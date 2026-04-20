"""Chat routes.

GET  /projects/{project_id}/chat/threads
POST /projects/{project_id}/chat/threads
GET  /projects/{project_id}/chat/threads/{tid}/messages
POST /projects/{project_id}/chat/threads/{tid}/messages  — SSE stream
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import ChatThread, ChatMessage, User
from ..services.chat_agent import ChatAgent

router = APIRouter(prefix="/projects", tags=["chat"])


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------

class ThreadSummary(BaseModel):
    id: str
    title: str | None
    created_at: str
    last_active_at: str


class ThreadCreate(BaseModel):
    title: str | None = None


class MessageSummary(BaseModel):
    id: str
    role: str
    content: str | None
    tool_calls: list | None
    edits_batch_id: str | None
    created_at: str


class SendMessage(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_thread(
    project_id: str,
    thread_id: str,
    user: User,
    session: AsyncSession,
) -> ChatThread:
    row = (await session.execute(
        sa.select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.project_id == project_id,
            ChatThread.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return row


async def _assert_project(project_id: str, user: User, session: AsyncSession) -> None:
    row = (await session.execute(
        sa.text("SELECT id FROM projects WHERE id=:pid AND owner_id=:uid"),
        {"pid": project_id, "uid": user.id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")


# ---------------------------------------------------------------------------
# LIST threads
# ---------------------------------------------------------------------------

@router.get("/{project_id}/chat/threads", response_model=list[ThreadSummary])
async def list_threads(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[ThreadSummary]:
    await _assert_project(project_id, user, session)
    rows = (await session.execute(
        sa.select(ChatThread)
        .where(ChatThread.project_id == project_id, ChatThread.user_id == user.id)
        .order_by(ChatThread.last_active_at.desc())
        .limit(50)
    )).scalars().all()
    return [
        ThreadSummary(
            id=r.id, title=r.title,
            created_at=r.created_at.isoformat(),
            last_active_at=r.last_active_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# CREATE thread
# ---------------------------------------------------------------------------

@router.post("/{project_id}/chat/threads", response_model=ThreadSummary, status_code=201)
async def create_thread(
    project_id: str,
    body: ThreadCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> ThreadSummary:
    await _assert_project(project_id, user, session)
    thread = ChatThread(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=user.id,
        title=body.title,
    )
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return ThreadSummary(
        id=thread.id, title=thread.title,
        created_at=thread.created_at.isoformat(),
        last_active_at=thread.last_active_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET messages
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/chat/threads/{thread_id}/messages",
    response_model=list[MessageSummary],
)
async def get_messages(
    project_id: str,
    thread_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[MessageSummary]:
    await _assert_thread(project_id, thread_id, user, session)
    rows = (await session.execute(
        sa.select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at)
    )).scalars().all()
    return [
        MessageSummary(
            id=r.id, role=r.role, content=r.content,
            tool_calls=r.tool_calls,
            edits_batch_id=r.edits_batch_id,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# SEND message — SSE stream
# ---------------------------------------------------------------------------

def _sse_frame(event_dict: dict) -> str:
    """Format a dict as a single SSE data frame."""
    return f"data: {json.dumps(event_dict)}\n\n"


@router.post("/{project_id}/chat/threads/{thread_id}/messages")
async def send_message(
    project_id: str,
    thread_id: str,
    body: SendMessage,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> StreamingResponse:
    await _assert_thread(project_id, thread_id, user, session)

    agent = ChatAgent(
        project_id=project_id,
        user_id=user.id,
        session=session,
    )

    async def event_generator() -> AsyncIterator[str]:
        async for event in agent.stream(thread_id, body.content):
            yield _sse_frame(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
