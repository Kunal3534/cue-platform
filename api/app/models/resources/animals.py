from __future__ import annotations

import enum
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class VetOnSet(str, enum.Enum):
    not_required = "not_required"
    standby = "standby"
    required = "required"


class AwbiStatus(str, enum.Enum):
    not_required = "not_required"
    exempt = "exempt"
    applied = "applied"
    pending = "pending"
    granted = "granted"
    denied = "denied"


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    species: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    handler_name: Mapped[str | None] = mapped_column(sa.String(500))
    handler_contact: Mapped[str | None] = mapped_column(sa.String(500))
    vet_on_set: Mapped[VetOnSet] = mapped_column(
        sa.Enum(VetOnSet, name="vet_on_set", create_type=False),
        server_default="not_required",
        nullable=False,
    )
    vet_name: Mapped[str | None] = mapped_column(sa.String(500))
    vet_contact: Mapped[str | None] = mapped_column(sa.String(500))
    awbi_status: Mapped[AwbiStatus] = mapped_column(
        sa.Enum(AwbiStatus, name="awbi_status", create_type=False),
        server_default="not_required",
        nullable=False,
    )
    awbi_number: Mapped[str | None] = mapped_column(sa.String(100))
    awbi_granted_at: Mapped[date | None] = mapped_column(sa.Date)
    awbi_applied_at: Mapped[date | None] = mapped_column(sa.Date)
    rest_window_hours: Mapped[int | None] = mapped_column(sa.Integer)
    insurance_inr: Mapped[int | None] = mapped_column(sa.Integer)
    welfare_notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DayAnimal(Base):
    __tablename__ = "day_animals"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    animal_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("animals.id", ondelete="CASCADE"), nullable=False
    )
    scene_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
