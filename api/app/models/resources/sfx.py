from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class SfxEffectKind(str, enum.Enum):
    fire = "fire"
    pyro = "pyro"
    squibs = "squibs"
    rain = "rain"
    wind = "wind"
    breakaway = "breakaway"
    fog = "fog"
    water = "water"
    explosion = "explosion"
    stunt_fight = "stunt_fight"
    stunt_fall = "stunt_fall"
    stunt_vehicle = "stunt_vehicle"
    stunt_water = "stunt_water"
    other = "other"


class SfxStatus(str, enum.Enum):
    planned = "planned"
    permit_pending = "permit_pending"
    cleared = "cleared"
    rehearsed = "rehearsed"
    executed = "executed"


class SfxEffect(Base):
    __tablename__ = "sfx_effects"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")
    )
    day_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="SET NULL")
    )
    effect_kind: Mapped[SfxEffectKind] = mapped_column(
        sa.Enum(SfxEffectKind, name="sfx_effect_kind", create_type=False), nullable=False
    )
    description: Mapped[str | None] = mapped_column(sa.Text)
    coordinator: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    coordinator_contact: Mapped[str | None] = mapped_column(sa.String(500))
    safety_plan_url: Mapped[str | None] = mapped_column(sa.Text)
    permits_required: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]", nullable=False)
    insurance_rider: Mapped[bool] = mapped_column(
        sa.Boolean, server_default="false", nullable=False
    )
    medic_required: Mapped[bool] = mapped_column(
        sa.Boolean, server_default="false", nullable=False
    )
    stunt_doubles: Mapped[list[Any] | None] = mapped_column(JSONB)
    rehearsal_date: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[SfxStatus] = mapped_column(
        sa.Enum(SfxStatus, name="sfx_status", create_type=False),
        server_default="planned",
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
