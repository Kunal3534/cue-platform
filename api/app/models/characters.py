from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(sa.String(500))
    actor_contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_principal: Mapped[bool] = mapped_column(sa.Boolean, server_default="false", nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("project_id", "canonical_name", name="uq_characters_project_canonical"),
    )
