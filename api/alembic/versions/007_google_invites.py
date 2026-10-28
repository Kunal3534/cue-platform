"""Google sign-in + Calendar sync + shoot invites.

users           — Google identity + offline Calendar access per user
days            — google_events: {email: calendar_event_id} for synced copies
shoot_invites   — people invited to a specific shoot day (crew, talent teams)

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token", sa.Text, nullable=True))
    op.add_column("users", sa.Column("google_calendar_connected", sa.Boolean,
                                     nullable=False, server_default=sa.false()))
    op.add_column("days", sa.Column("google_events", pg.JSONB, nullable=True))

    op.create_table(
        "shoot_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="invited"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invites_project_date", "shoot_invites", ["project_id", "date"])
    op.create_unique_constraint("uq_invites_project_date_email", "shoot_invites",
                                ["project_id", "date", "email"])


def downgrade() -> None:
    op.drop_table("shoot_invites")
    op.drop_column("days", "google_events")
    op.drop_column("users", "google_calendar_connected")
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "google_sub")
