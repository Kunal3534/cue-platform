from __future__ import annotations

import enum
from datetime import datetime, date, time

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class DayKind(str, enum.Enum):
    shoot = "shoot"
    travel = "travel"
    off = "off"
    hold = "hold"
    buffer = "buffer"
    prep = "prep"


class SceneDN(str, enum.Enum):
    day = "day"
    night = "night"
    day_int = "day_int"
    night_int = "night_int"
    dusk = "dusk"


class SceneStatus(str, enum.Enum):
    planned = "planned"
    shot = "shot"
    omitted = "omitted"
    pickup_needed = "pickup_needed"


class SceneCharRole(str, enum.Enum):
    speaking = "speaking"
    non_speaking = "non_speaking"
    featured = "featured"
    background = "background"


class DaySceneActualStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    shot = "shot"
    omitted_today = "omitted_today"


class Day(Base):
    __tablename__ = "days"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    shoot_day_number: Mapped[int | None] = mapped_column(sa.Integer)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    kind: Mapped[DayKind] = mapped_column(
        sa.Enum(DayKind, name="day_kind", create_type=False), nullable=False
    )
    shift_start: Mapped[time | None] = mapped_column(sa.Time)
    shift_end: Mapped[time | None] = mapped_column(sa.Time)
    primary_location_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("locations.id")
    )
    banner_text: Mapped[str | None] = mapped_column(sa.Text)
    sunrise: Mapped[time | None] = mapped_column(sa.Time)
    sunset: Mapped[time | None] = mapped_column(sa.Time)
    golden_hour_start: Mapped[time | None] = mapped_column(sa.Time)
    golden_hour_end: Mapped[time | None] = mapped_column(sa.Time)
    weather: Mapped[dict | None] = mapped_column(sa.JSON)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("project_id", "date", name="uq_days_project_date"),
        sa.Index("ix_days_project_shoot_day", "project_id", "shoot_day_number"),
    )


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_number: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(500))
    description: Mapped[str | None] = mapped_column(sa.Text)
    page_eighths: Mapped[int | None] = mapped_column(sa.Integer)
    setups_est: Mapped[int] = mapped_column(sa.Integer, server_default="0", nullable=False)
    dn: Mapped[SceneDN] = mapped_column(
        sa.Enum(SceneDN, name="scene_dn", create_type=False), nullable=False
    )
    location_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("locations.id")
    )
    act: Mapped[int | None] = mapped_column(sa.Integer)
    sequence: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[SceneStatus] = mapped_column(
        sa.Enum(SceneStatus, name="scene_status", create_type=False),
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

    __table_args__ = (
        sa.UniqueConstraint("project_id", "scene_number", name="uq_scenes_project_number"),
    )


class DayScene(Base):
    __tablename__ = "day_scenes"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    day_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False
    )
    order_in_day: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    estimated_start: Mapped[time | None] = mapped_column(sa.Time)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(sa.Integer)
    actual_status: Mapped[DaySceneActualStatus] = mapped_column(
        sa.Enum(DaySceneActualStatus, name="day_scene_status", create_type=False),
        server_default="scheduled",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("day_id", "scene_id", name="uq_day_scenes"),
        sa.Index("ix_day_scenes_scene_id", "scene_id"),
    )


class SceneCharacter(Base):
    __tablename__ = "scene_characters"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    scene_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[SceneCharRole] = mapped_column(
        sa.Enum(SceneCharRole, name="scene_char_role", create_type=False), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("scene_id", "character_id", name="uq_scene_characters"),
    )
