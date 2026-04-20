from __future__ import annotations

import enum
from datetime import datetime, time
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class HmuCategory(str, enum.Enum):
    straight = "straight"
    prosthetic = "prosthetic"
    wound_sfx = "wound_sfx"
    de_age = "de_age"
    aged = "aged"
    aging = "aging"
    dental = "dental"
    hair_piece = "hair_piece"


class HmuSession(Base):
    __tablename__ = "hmu_sessions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    look_id: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    category: Mapped[HmuCategory] = mapped_column(
        sa.Enum(HmuCategory, name="hmu_category", create_type=False), nullable=False
    )
    apply_minutes: Mapped[int | None] = mapped_column(sa.Integer)
    remove_minutes: Mapped[int | None] = mapped_column(sa.Integer)
    hmu_call_time: Mapped[time | None] = mapped_column(sa.Time)
    artist_lead: Mapped[str | None] = mapped_column(sa.String(500))
    artist_vendor: Mapped[str | None] = mapped_column(sa.String(500))
    mold_sessions: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]", nullable=False)
    continuity_ref: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "character_id", "day_id", "look_id", name="uq_hmu_sessions_char_day_look"
        ),
    )
