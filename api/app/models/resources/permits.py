from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class PermitKind(str, enum.Enum):
    location = "location"
    road_rto = "road_rto"
    fire = "fire"
    aerial_dgca = "aerial_dgca"
    coastal = "coastal"
    animal_awbi = "animal_awbi"
    closed_set = "closed_set"
    heritage_asi = "heritage_asi"
    police = "police"
    panchayat = "panchayat"
    other = "other"


class PermitStatus(str, enum.Enum):
    not_applied = "not_applied"
    applied = "applied"
    pending = "pending"
    granted = "granted"
    denied = "denied"
    expired = "expired"


class Permit(Base):
    __tablename__ = "permits"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[PermitKind] = mapped_column(
        sa.Enum(PermitKind, name="permit_kind", create_type=False), nullable=False
    )
    issuing_body: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(sa.String(100))
    applied_at: Mapped[date | None] = mapped_column(sa.Date)
    granted_at: Mapped[date | None] = mapped_column(sa.Date)
    expires_at: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[PermitStatus] = mapped_column(
        sa.Enum(PermitStatus, name="permit_status", create_type=False),
        server_default="not_applied",
        nullable=False,
    )
    fee_inr: Mapped[int | None] = mapped_column(sa.Integer)
    related_location_id: Mapped[str | None] = mapped_column(sa.String(36))
    related_day_ids: Mapped[list[str] | None] = mapped_column(ARRAY(sa.String(36)))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
