from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class ProjectStatus(str, enum.Enum):
    pre = "pre"
    shoot = "shoot"
    wrap = "wrap"
    archived = "archived"


class LocationKind(str, enum.Enum):
    ext = "ext"
    int = "int"
    studio = "studio"
    practical = "practical"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    window: Mapped[str | None] = mapped_column(sa.String(500))
    start_date: Mapped[date | None] = mapped_column(sa.Date)
    end_date: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[ProjectStatus] = mapped_column(
        sa.Enum(ProjectStatus, name="project_status", create_type=False),
        server_default="pre",
        nullable=False,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )
    source_file: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(sa.String(500))
    live_scenario_id: Mapped[str | None] = mapped_column(sa.String(36))
    # parsed_json kept until migration 003 drops it; v0.1 routes still read it
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    area: Mapped[str | None] = mapped_column(sa.String(500))
    address: Mapped[str | None] = mapped_column(sa.Text)
    lat: Mapped[float | None] = mapped_column(sa.Numeric(10, 6))
    lng: Mapped[float | None] = mapped_column(sa.Numeric(10, 6))
    kind: Mapped[LocationKind] = mapped_column(
        sa.Enum(LocationKind, name="location_kind", create_type=False), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
