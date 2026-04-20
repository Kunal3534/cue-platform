from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class CameraKind(str, enum.Enum):
    camera = "camera"
    lighting = "lighting"
    grip = "grip"
    special = "special"
    drone = "drone"
    steadi = "steadi"
    jib = "jib"


class CameraUnit(Base):
    __tablename__ = "camera_units"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    unit_code: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    kind: Mapped[CameraKind] = mapped_column(
        sa.Enum(CameraKind, name="camera_kind", create_type=False), nullable=False
    )
    description: Mapped[str | None] = mapped_column(sa.Text)
    rental_vendor: Mapped[str | None] = mapped_column(sa.String(500))
    operator_name: Mapped[str | None] = mapped_column(sa.String(500))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("project_id", "unit_code", name="uq_camera_units_project_code"),
    )


class CameraDayUse(Base):
    __tablename__ = "camera_day_uses"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    camera_unit_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("camera_units.id", ondelete="CASCADE"), nullable=False
    )
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    count: Mapped[int] = mapped_column(sa.Integer, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("camera_unit_id", "day_id", name="uq_camera_day_uses"),
    )
