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

    if "ix_theory_topics_grade" in indexes:
        op.drop_index("ix_theory_topics_grade", table_name="theory_topics")

    if bind.dialect.name == "sqlite":
        # SQLite cannot drop columns and constraints directly, so recreate the table.
        with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
            if "uq_theory_topics_grade_slug" in constraints:
                batch_op.drop_constraint("uq_theory_topics_grade_slug", type_="unique")
            batch_op.drop_column("grade")
            batch_op.drop_column("title")
            batch_op.create_unique_constraint("uq_theory_topics_slug", ["slug"])
        return

    # PostgreSQL supports these operations directly. Recreating the table would
    # temporarily drop its primary key and break foreign-key dependencies.
    if "uq_theory_topics_grade_slug" in constraints:
        op.drop_constraint(
            "uq_theory_topics_grade_slug",
            "theory_topics",
            type_="unique",
        )
    op.drop_column("theory_topics", "grade")
    op.drop_column("theory_topics", "title")
    op.create_unique_constraint(
        "uq_theory_topics_slug",
        "theory_topics",
        ["slug"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("grade", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
            batch_op.drop_constraint("uq_theory_topics_slug", type_="unique")
            batch_op.create_unique_constraint(
                "uq_theory_topics_grade_slug",
                ["grade", "slug"],
            )
        return

    op.add_column(
        "theory_topics",
        sa.Column("grade", sa.Integer(), nullable=True),
    )
    op.add_column(
        "theory_topics",
        sa.Column("title", sa.String(length=255), nullable=True),
    )
    op.drop_constraint("uq_theory_topics_slug", "theory_topics", type_="unique")
    op.create_unique_constraint(
        "uq_theory_topics_grade_slug",
        "theory_topics",
        ["grade", "slug"],
    )
