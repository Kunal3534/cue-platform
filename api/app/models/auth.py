from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..db import Base


class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    token: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ShareToken(Base):
    __tablename__ = "share_tokens"

    token: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("projects.id"), nullable=False
    )
    view: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
