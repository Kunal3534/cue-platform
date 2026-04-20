from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(sa.String(500))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.Index("ix_chat_threads_project_active", "project_id", "last_active_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ChatRole] = mapped_column(
        sa.Enum(ChatRole, name="chat_role", create_type=False), nullable=False
    )
    content: Mapped[str | None] = mapped_column(sa.Text)
    tool_calls: Mapped[list[Any] | None] = mapped_column(JSONB)
    tool_results: Mapped[list[Any] | None] = mapped_column(JSONB)
    edits_batch_id: Mapped[str | None] = mapped_column(sa.String(36))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.Index("ix_chat_messages_thread_created", "thread_id", "created_at"),
    )
