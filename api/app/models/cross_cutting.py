from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class CallsheetStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    sent = "sent"
    distributed = "distributed"
    stale = "stale"


class FlagKind(str, enum.Enum):
    cast_hold = "cast_hold"
    permit_lead = "permit_lead"
    weather = "weather"
    drone_block = "drone_block"
    insurance = "insurance"
    continuity = "continuity"
    vendor = "vendor"
    capacity = "capacity"
    missing_data = "missing_data"
    cost_overrun = "cost_overrun"
    safety = "safety"
    custom = "custom"


class FlagSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    blocker = "blocker"


class FlagRaisedBy(str, enum.Enum):
    system = "system"
    user = "user"


class PropagationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    discarded = "discarded"
    expired = "expired"


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    parent_scenario_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenarios.id")
    )
    is_live: Mapped[bool] = mapped_column(sa.Boolean, server_default="false", nullable=False)
    created_by: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    forked_at_batch: Mapped[str | None] = mapped_column(sa.String(36))
    merged_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    discarded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CallSheet(Base):
    __tablename__ = "call_sheets"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[CallsheetStatus] = mapped_column(
        sa.Enum(CallsheetStatus, name="callsheet_status", create_type=False),
        server_default="draft",
        nullable=False,
    )
    pdf_s3_key: Mapped[str | None] = mapped_column(sa.Text)
    generated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    generated_by: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sent_to: Mapped[list[Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("day_id", "version", name="uq_call_sheets_day_version"),
        sa.Index("ix_call_sheets_day_version", "day_id", "version"),
    )


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[FlagKind] = mapped_column(
        sa.Enum(FlagKind, name="flag_kind", create_type=False), nullable=False
    )
    severity: Mapped[FlagSeverity] = mapped_column(
        sa.Enum(FlagSeverity, name="flag_severity", create_type=False), nullable=False
    )
    related_scene_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")
    )
    related_day_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="SET NULL")
    )
    related_character_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("characters.id", ondelete="SET NULL")
    )
    related_resource_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    raised_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    raised_by: Mapped[FlagRaisedBy] = mapped_column(
        sa.Enum(FlagRaisedBy, name="flag_raised_by", create_type=False), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    dismissed: Mapped[bool] = mapped_column(sa.Boolean, server_default="false", nullable=False)

    __table_args__ = (
        sa.Index("ix_flags_open", "project_id", "severity", "resolved_at"),
    )


class Edit(Base):
    __tablename__ = "edits"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    entity_table: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(sa.String(36), nullable=False)
    field: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    propagated: Mapped[bool] = mapped_column(sa.Boolean, server_default="false", nullable=False)

    __table_args__ = (
        sa.Index("ix_edits_batch_id", "batch_id"),
        sa.Index("ix_edits_project_created", "project_id", "created_at"),
    )


class PropagationPreview(Base):
    __tablename__ = "propagation_previews"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[PropagationStatus] = mapped_column(
        sa.Enum(PropagationStatus, name="propagation_status", create_type=False),
        server_default="pending",
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ViewCache(Base):
    __tablename__ = "view_cache"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    view_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
