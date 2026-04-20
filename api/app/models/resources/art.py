from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class ArtStatus(str, enum.Enum):
    planned = "planned"
    designing = "designing"
    building = "building"
    ready = "ready"
    struck = "struck"
    returned = "returned"


class ArtBuild(Base):
    __tablename__ = "art_builds"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    scenes_raw: Mapped[str | None] = mapped_column(sa.Text)
    days_ref: Mapped[list[str] | None] = mapped_column(ARRAY(sa.String(36)))
    build_days_lead: Mapped[int | None] = mapped_column(sa.Integer)
    art_dir: Mapped[str | None] = mapped_column(sa.String(500))
    status: Mapped[ArtStatus] = mapped_column(
        sa.Enum(ArtStatus, name="art_status", create_type=False),
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
