"""add teacher invites table

Revision ID: 0009_teacher_invites
Revises: 0008_roles_and_teacher_groups
Create Date: 2026-05-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_teacher_invites"
down_revision: str | None = "0008_roles_and_teacher_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teacher_invites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_teacher_invites_code_hash",
        "teacher_invites",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        "ix_teacher_invites_created_by_admin_id",
        "teacher_invites",
        ["created_by_admin_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_teacher_invites_created_by_admin_id",
        table_name="teacher_invites",
    )
    op.drop_index(
        "ix_teacher_invites_code_hash",
        table_name="teacher_invites",
    )
    op.drop_table("teacher_invites")
