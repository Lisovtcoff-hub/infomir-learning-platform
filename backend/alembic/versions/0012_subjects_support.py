"""add subject to categories tasks variants

Revision ID: 0012_subjects_support
Revises: 0011_teacher_withdrawals
Create Date: 2026-05-15 16:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0012_subjects_support"
down_revision: str | None = "0011_teacher_withdrawals"
branch_labels = None
depends_on = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return any(item["name"] == column_name for item in sa.inspect(bind).get_columns(table_name))


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    unique_constraints = inspector.get_unique_constraints(table_name)
    return any(item.get("name") == index_name for item in [*indexes, *unique_constraints])


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, "task_categories", "subject"):
        op.add_column("task_categories", sa.Column("subject", sa.String(length=50), nullable=True))
    if not _has_column(bind, "tasks", "subject"):
        op.add_column("tasks", sa.Column("subject", sa.String(length=50), nullable=True))
    if not _has_column(bind, "variants", "subject"):
        op.add_column("variants", sa.Column("subject", sa.String(length=50), nullable=True))

    bind.execute(sa.text("UPDATE task_categories SET subject = 'informatics' WHERE subject IS NULL OR subject = ''"))
    bind.execute(sa.text("UPDATE tasks SET subject = 'informatics' WHERE subject IS NULL OR subject = ''"))
    bind.execute(sa.text("UPDATE variants SET subject = 'informatics' WHERE subject IS NULL OR subject = ''"))

    with op.batch_alter_table("task_categories") as batch_op:
        batch_op.alter_column("subject", existing_type=sa.String(length=50), nullable=False, server_default="informatics")

    if not _has_index(bind, "task_categories", "uq_task_categories_code_grade_exam_subject"):
        op.create_index(
            "uq_task_categories_code_grade_exam_subject",
            "task_categories",
            ["code", "grade", "exam_type", "subject"],
            unique=True,
        )
    if not _has_index(bind, "task_categories", "uq_task_categories_title_grade_exam_subject"):
        op.create_index(
            "uq_task_categories_title_grade_exam_subject",
            "task_categories",
            ["title", "grade", "exam_type", "subject"],
            unique=True,
        )

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("subject", existing_type=sa.String(length=50), nullable=False, server_default="informatics")
    if not _has_index(bind, "tasks", "ix_tasks_subject"):
        op.create_index("ix_tasks_subject", "tasks", ["subject"], unique=False)

    with op.batch_alter_table("variants") as batch_op:
        batch_op.alter_column("subject", existing_type=sa.String(length=50), nullable=False, server_default="informatics")
    if not _has_index(bind, "variants", "ix_variants_subject"):
        op.create_index("ix_variants_subject", "variants", ["subject"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    if _has_index(bind, "variants", "ix_variants_subject"):
        op.drop_index("ix_variants_subject", table_name="variants")
    if _has_index(bind, "tasks", "ix_tasks_subject"):
        op.drop_index("ix_tasks_subject", table_name="tasks")
    if _has_index(bind, "task_categories", "uq_task_categories_code_grade_exam_subject"):
        op.drop_index("uq_task_categories_code_grade_exam_subject", table_name="task_categories")
    if _has_index(bind, "task_categories", "uq_task_categories_title_grade_exam_subject"):
        op.drop_index("uq_task_categories_title_grade_exam_subject", table_name="task_categories")

    with op.batch_alter_table("variants") as batch_op:
        batch_op.drop_column("subject")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("subject")
    with op.batch_alter_table("task_categories") as batch_op:
        batch_op.drop_column("subject")
