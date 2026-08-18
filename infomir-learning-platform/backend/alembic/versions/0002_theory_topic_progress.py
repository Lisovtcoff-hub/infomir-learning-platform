"""add theory topic progress

Revision ID: 0002_theory_topic_progress
Revises: 0001_initial_schema
Create Date: 2026-05-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_theory_topic_progress"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "theory_topic_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("theory_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_theory_topic_progress_user_topic"),
    )
    op.create_index("ix_theory_topic_progress_user_id", "theory_topic_progress", ["user_id"])
    op.create_index("ix_theory_topic_progress_topic_id", "theory_topic_progress", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_theory_topic_progress_topic_id", table_name="theory_topic_progress")
    op.drop_index("ix_theory_topic_progress_user_id", table_name="theory_topic_progress")
    op.drop_table("theory_topic_progress")
