"""add teacher withdrawals

Revision ID: 0011_teacher_withdrawals
Revises: 0010_student_access_code
Create Date: 2026-05-12 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0011_teacher_withdrawals"
down_revision: str | None = "0010_student_access_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_withdrawals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teacher_withdrawals_teacher_id", "teacher_withdrawals", ["teacher_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_teacher_withdrawals_teacher_id", table_name="teacher_withdrawals")
    op.drop_table("teacher_withdrawals")
