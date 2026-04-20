from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class VehicleSource(str, enum.Enum):
    rental = "rental"
    owned = "owned"
    local_hired = "local_hired"
    loan = "loan"


class PictureVehicle(Base):
    __tablename__ = "picture_vehicles"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    spec: Mapped[str | None] = mapped_column(sa.Text)
    source: Mapped[VehicleSource | None] = mapped_column(
        sa.Enum(VehicleSource, name="vehicle_source", create_type=False)
    )
    source_vendor: Mapped[str | None] = mapped_column(sa.String(500))
    driver_name: Mapped[str | None] = mapped_column(sa.String(500))
    driver_contact: Mapped[str | None] = mapped_column(sa.String(500))
    insurance_inr: Mapped[int | None] = mapped_column(sa.Integer)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VehicleDayUse(Base):
    __tablename__ = "vehicle_day_uses"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("picture_vehicles.id", ondelete="CASCADE"), nullable=False
    )
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    count: Mapped[int] = mapped_column(sa.Integer, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("vehicle_id", "day_id", name="uq_vehicle_day_uses"),
    )
