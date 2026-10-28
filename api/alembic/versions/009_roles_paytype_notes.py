"""Member roles, expense pay-type, private day notes.

workspace_members.role — producer (full edit) | contributor (view + own notes)
expenses.pay_type      — cash_advance | contributor_payment (Shubhra's split)
user_day_notes         — per-user private notes on a shoot day

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_members",
                  sa.Column("role", sa.String(16), nullable=False, server_default="contributor"))
    op.add_column("expenses", sa.Column("pay_type", sa.String(24), nullable=True))

    op.create_table(
        "user_day_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("text", sa.Text, nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_day_notes_pde", "user_day_notes",
                                ["project_id", "date", "user_email"])


def downgrade() -> None:
    op.drop_table("user_day_notes")
    op.drop_column("expenses", "pay_type")
    op.drop_column("workspace_members", "role")
