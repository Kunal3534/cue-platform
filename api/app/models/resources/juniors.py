from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class JrGrade(str, enum.Enum):
    junior = "junior"
    sr = "sr"
    specialist = "specialist"
    dancer = "dancer"
    musician = "musician"


class JrStatus(str, enum.Enum):
    planned = "planned"
    briefed = "briefed"
    confirmed = "confirmed"
    on_set = "on_set"


class JuniorArtistCall(Base):
    __tablename__ = "junior_artist_calls"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    grade: Mapped[JrGrade] = mapped_column(
        sa.Enum(JrGrade, name="jr_grade", create_type=False), nullable=False
    )
    context: Mapped[str | None] = mapped_column(sa.Text)
    wardrobe_notes: Mapped[str | None] = mapped_column(sa.Text)
    vendor_name: Mapped[str | None] = mapped_column(sa.String(500))
    vendor_contact: Mapped[str | None] = mapped_column(sa.String(500))
    meal_plan_required: Mapped[bool] = mapped_column(
        sa.Boolean, server_default="false", nullable=False
    )
    status: Mapped[JrStatus] = mapped_column(
        sa.Enum(JrStatus, name="jr_status", create_type=False),
        server_default="planned",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("day_id", "grade", name="uq_jr_calls_day_grade"),
    )
