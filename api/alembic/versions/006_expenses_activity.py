"""Expenses + activity log.

expenses      — producer-only shoot expenses: a receipt image/PDF in object
                storage (auto-read into structured fields by the worker) or a
                manually entered line. Tagged to a shoot date, never shared.
activity_log  — who changed what, when. Multiple producers edit the same
                board, so every mutation records its author.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=True),  # shoot day this is tagged to
        sa.Column("vendor", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),  # manual | receipt
        sa.Column("s3_key", sa.Text, nullable=True),
        sa.Column("filename", sa.Text, nullable=True),
        sa.Column("content_type", sa.Text, nullable=True),
        # processing → worker is reading the receipt; ready → done;
        # needs_review → auto-read failed or was unavailable
        sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
        sa.Column("extracted", pg.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expenses_project_date", "expenses", ["project_id", "date"])

    op.create_table(
        "activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("detail", pg.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_activity_project_created", "activity_log", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_project_created", table_name="activity_log")
    op.drop_table("activity_log")
    op.drop_index("ix_expenses_project_date", table_name="expenses")
    op.drop_table("expenses")
