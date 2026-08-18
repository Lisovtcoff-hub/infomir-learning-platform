"""drop grade/title from theory_topics

Revision ID: 0005_drop_grade_title_from_theory_topics
Revises: 0004_single_topic_source_constraints
Create Date: 2026-05-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_drop_grade_title_from_theory_topics"
down_revision: str | None = "0004_single_topic_source_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("theory_topics")}
    constraints = {uc["name"] for uc in inspector.get_unique_constraints("theory_topics")}

    # Remove legacy grade index before batch copy (SQLite).
    if "ix_theory_topics_grade" in indexes:
        op.drop_index("ix_theory_topics_grade", table_name="theory_topics")

    with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
        if "uq_theory_topics_grade_slug" in constraints:
            batch_op.drop_constraint("uq_theory_topics_grade_slug", type_="unique")
        batch_op.drop_column("grade")
        batch_op.drop_column("title")
        batch_op.create_unique_constraint("uq_theory_topics_slug", ["slug"])


def downgrade() -> None:
    with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("grade", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch_op.drop_constraint("uq_theory_topics_slug", type_="unique")
        batch_op.create_unique_constraint("uq_theory_topics_grade_slug", ["grade", "slug"])
