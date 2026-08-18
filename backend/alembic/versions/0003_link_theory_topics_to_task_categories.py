"""link theory topics to task categories

Revision ID: 0003_link_theory_topics_to_task_categories
Revises: 0002_theory_topic_progress
Create Date: 2026-05-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_link_theory_topics_to_task_categories"
down_revision: str | None = "0002_theory_topic_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("theory_topics")}
    indexes = {idx["name"] for idx in inspector.get_indexes("theory_topics")}

    if "category_id" not in columns:
        op.add_column("theory_topics", sa.Column("category_id", sa.Integer(), nullable=True))
    if "ix_theory_topics_category_id" not in indexes:
        op.create_index("ix_theory_topics_category_id", "theory_topics", ["category_id"])

    if bind.dialect.name != "sqlite":
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys("theory_topics")}
        if "fk_theory_topics_category_id_task_categories" not in fk_names:
            op.create_foreign_key(
                "fk_theory_topics_category_id_task_categories",
                "theory_topics",
                "task_categories",
                ["category_id"],
                ["id"],
                ondelete="SET NULL",
            )

    rows = bind.execute(sa.text("SELECT id, grade, title, sort_order FROM theory_topics")).fetchall()
    for row in rows:
        topic_id = int(row.id)
        grade = int(row.grade)
        title = str(row.title)
        sort_order = int(row.sort_order or 0)
        exam_type = "oge" if grade == 9 else "vpr"
        code = f"topic_{grade}_{topic_id}"

        category_row = bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_categories
                WHERE grade = :grade AND exam_type = :exam_type AND lower(title) = lower(:title)
                LIMIT 1
                """
            ),
            {"grade": grade, "exam_type": exam_type, "title": title},
        ).fetchone()

        if category_row is None:
            category_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO task_categories (code, title, exam_type, grade, description, sort_order)
                    VALUES (:code, :title, :exam_type, :grade, :description, :sort_order)
                    RETURNING id
                    """
                ),
                {
                    "code": code,
                    "title": title,
                    "exam_type": exam_type,
                    "grade": grade,
                    "description": "Автосоздано миграцией для связи теории и тренировок",
                    "sort_order": sort_order,
                },
            ).scalar_one()
        else:
            category_id = int(category_row.id)

        bind.execute(
            sa.text("UPDATE theory_topics SET category_id = :category_id WHERE id = :topic_id"),
            {"category_id": category_id, "topic_id": topic_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("theory_topics")}
    indexes = {idx["name"] for idx in inspector.get_indexes("theory_topics")}

    if bind.dialect.name != "sqlite":
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys("theory_topics")}
        if "fk_theory_topics_category_id_task_categories" in fk_names:
            op.drop_constraint("fk_theory_topics_category_id_task_categories", "theory_topics", type_="foreignkey")
    if "ix_theory_topics_category_id" in indexes:
        op.drop_index("ix_theory_topics_category_id", table_name="theory_topics")
    if "category_id" in columns:
        op.drop_column("theory_topics", "category_id")
