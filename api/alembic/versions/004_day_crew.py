"""Add days.crew — per-day crew assignments (photographer, video, etc.).

Editorial shoots are crew-light: a JSONB map keyed by role is enough and
avoids a whole crew table while the product is this young.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("days", sa.Column("crew", pg.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("days", "crew")
