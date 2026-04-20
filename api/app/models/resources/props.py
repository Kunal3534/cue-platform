from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class PropCategory(str, enum.Enum):
    hero_critical = "hero_critical"
    hero = "hero"
    set_dress = "set_dress"
    background = "background"
    food = "food"
    paper_prop = "paper_prop"


class PropSource(str, enum.Enum):
    build_inhouse = "build_inhouse"
    build_studio = "build_studio"
    rental = "rental"
    owned = "owned"
    local_sourced = "local_sourced"
    purchased = "purchased"


class PropStatus(str, enum.Enum):
    planned = "planned"
    ordered = "ordered"
    in_progress = "in_progress"
    ready = "ready"
    on_set = "on_set"
    returned = "returned"


class PropSceneRole(str, enum.Enum):
    hero = "hero"
    set_dress = "set_dress"
    action_prop = "action_prop"
    bg = "bg"


class Prop(Base):
    __tablename__ = "props"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    category: Mapped[PropCategory] = mapped_column(
        sa.Enum(PropCategory, name="prop_category", create_type=False), nullable=False
    )
    scenes_raw: Mapped[str | None] = mapped_column(sa.Text)
    source: Mapped[PropSource | None] = mapped_column(
        sa.Enum(PropSource, name="prop_source", create_type=False)
    )
    source_vendor: Mapped[str | None] = mapped_column(sa.String(500))
    lead_days: Mapped[int | None] = mapped_column(sa.Integer)
    insurance_inr: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[PropStatus] = mapped_column(
        sa.Enum(PropStatus, name="prop_status", create_type=False),
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


class SceneProp(Base):
    __tablename__ = "scene_props"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    scene_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False
    )
    prop_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[PropSceneRole] = mapped_column(
        sa.Enum(PropSceneRole, name="prop_scene_role", create_type=False), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("scene_id", "prop_id", name="uq_scene_props"),
    )
