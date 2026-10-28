"""Workspace members — app-managed team access per workspace.

Until now the team was the ALLOWED_EMAILS env allowlist. Members added here
can sign in (Google or magic link) and edit everything in that workspace,
no redeploy needed.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("added_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_members_project", "workspace_members", ["project_id"])
    op.create_index("ix_members_email", "workspace_members", ["email"])
    op.create_unique_constraint("uq_members_project_email", "workspace_members",
                                ["project_id", "email"])


def downgrade() -> None:
    op.drop_table("workspace_members")
