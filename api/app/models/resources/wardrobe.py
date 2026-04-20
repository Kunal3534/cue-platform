from __future__ import annotations

import enum
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db import Base


class WardrobeEra(str, enum.Enum):
    now = "now"
    era_1994 = "1994"
    era_2008 = "2008"
    flashback = "flashback"
    other = "other"


class WardrobeSource(str, enum.Enum):
    in_house = "in_house"
    tailored = "tailored"
    rental = "rental"
    sourced_flea = "sourced_flea"
    govt_spec = "govt_spec"
    purchased = "purchased"


class WardrobeLook(Base):
    __tablename__ = "wardrobe_looks"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    look_id: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    era: Mapped[WardrobeEra] = mapped_column(
        sa.Enum(WardrobeEra, name="wardrobe_era", create_type=False), nullable=False
    )
    era_label: Mapped[str | None] = mapped_column(sa.String(100))
    scenes_raw: Mapped[str | None] = mapped_column(sa.Text)
    multiples_count: Mapped[int] = mapped_column(sa.Integer, server_default="1", nullable=False)
    source: Mapped[WardrobeSource | None] = mapped_column(
        sa.Enum(WardrobeSource, name="wardrobe_source", create_type=False)
    )
    source_vendor: Mapped[str | None] = mapped_column(sa.String(500))
    return_by: Mapped[date | None] = mapped_column(sa.Date)
    continuity_key: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("character_id", "look_id", name="uq_wardrobe_looks_char_look"),
    )
