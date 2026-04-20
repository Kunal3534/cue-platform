from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class VfxShotType(str, enum.Enum):
    sky_grade = "sky_grade"
    crowd_aug = "crowd_aug"
    greenscreen = "greenscreen"
    cleanup = "cleanup"
    drone_replace = "drone_replace"
    muzzle_flash = "muzzle_flash"
    aging_blend = "aging_blend"
    period_cleanup = "period_cleanup"
    rotoscope = "rotoscope"
    other = "other"


class VfxComplexity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    hero = "hero"


class VfxBidStatus(str, enum.Enum):
    estimated = "estimated"
    bidded = "bidded"
    extended = "extended"
    cancelled = "cancelled"


class VfxStatus(str, enum.Enum):
    planned = "planned"
    plates_delivered = "plates_delivered"
    comp_started = "comp_started"
    review = "review"
    delivered = "delivered"
    final = "final"


class VfxShot(Base):
    __tablename__ = "vfx_shots"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")
    )
    shot_number: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    shot_type: Mapped[VfxShotType] = mapped_column(
        sa.Enum(VfxShotType, name="vfx_shot_type", create_type=False), nullable=False
    )
    complexity: Mapped[VfxComplexity] = mapped_column(
        sa.Enum(VfxComplexity, name="vfx_complexity", create_type=False), nullable=False
    )
    plates_required: Mapped[int] = mapped_column(sa.Integer, server_default="1", nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    vendor_name: Mapped[str | None] = mapped_column(sa.String(500))
    budget_inr: Mapped[int | None] = mapped_column(sa.Integer)
    bid_status: Mapped[VfxBidStatus | None] = mapped_column(
        sa.Enum(VfxBidStatus, name="vfx_bid_status", create_type=False)
    )
    status: Mapped[VfxStatus] = mapped_column(
        sa.Enum(VfxStatus, name="vfx_status", create_type=False),
        server_default="planned",
        nullable=False,
    )
    markers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("project_id", "shot_number", name="uq_vfx_shots_project_number"),
    )
