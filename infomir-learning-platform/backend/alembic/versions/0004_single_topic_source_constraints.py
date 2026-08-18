"""single topic source constraints

Revision ID: 0004_single_topic_source_constraints
Revises: 0003_link_theory_topics_to_task_categories
Create Date: 2026-05-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_single_topic_source_constraints"
down_revision: str | None = "0003_link_theory_topics_to_task_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cat_indexes = {idx["name"] for idx in inspector.get_indexes("task_categories")}
    theory_indexes = {idx["name"] for idx in inspector.get_indexes("theory_topics")}

    if "uq_task_categories_title_grade_exam" not in cat_indexes:
        op.create_index(
            "uq_task_categories_title_grade_exam",
            "task_categories",
            ["title", "grade", "exam_type"],
            unique=True,
        )

    if "uq_theory_topics_category_id" not in theory_indexes:
        op.create_index(
            "uq_theory_topics_category_id",
            "theory_topics",
            ["category_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cat_indexes = {idx["name"] for idx in inspector.get_indexes("task_categories")}
    theory_indexes = {idx["name"] for idx in inspector.get_indexes("theory_topics")}

    if "uq_theory_topics_category_id" in theory_indexes:
        op.drop_index("uq_theory_topics_category_id", table_name="theory_topics")
    if "uq_task_categories_title_grade_exam" in cat_indexes:
        op.drop_index("uq_task_categories_title_grade_exam", table_name="task_categories")
