"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("school", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.create_table(
        "theory_topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("tip", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("grade", "slug", name="uq_theory_topics_grade_slug"),
    )
    op.create_index("ix_theory_topics_grade", "theory_topics", ["grade"])
    op.create_index("ix_theory_topics_slug", "theory_topics", ["slug"])

    op.create_table(
        "theory_concepts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("theory_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_theory_concepts_topic_id", "theory_concepts", ["topic_id"])

    op.create_table(
        "task_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_type", sa.String(length=50), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code", "grade", "exam_type", name="uq_task_categories_code_grade_exam"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("task_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("exam_type", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tasks_grade", "tasks", ["grade"])
    op.create_index("ix_tasks_exam_type", "tasks", ["exam_type"])
    op.create_index("ix_tasks_category_id", "tasks", ["category_id"])

    op.create_table(
        "task_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_task_options_task_id", "task_options", ["task_id"])

    op.create_table(
        "variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_type", sa.String(length=50), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_variants_exam_type", "variants", ["exam_type"])
    op.create_index("ix_variants_grade", "variants", ["grade"])

    op.create_table(
        "variant_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_variant_tasks_variant_id", "variant_tasks", ["variant_id"])
    op.create_index("ix_variant_tasks_task_id", "variant_tasks", ["task_id"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("variants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grade_mark", sa.Integer(), nullable=True),
    )
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"])
    op.create_index("ix_attempts_variant_id", "attempts", ["variant_id"])

    op.create_table(
        "attempt_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_attempt_answers_attempt_id", "attempt_answers", ["attempt_id"])
    op.create_index("ix_attempt_answers_task_id", "attempt_answers", ["task_id"])

    op.create_table(
        "tariffs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_tariffs_code"),
    )
    op.create_index("ix_tariffs_code", "tariffs", ["code"])

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tariff_id", sa.Integer(), sa.ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
    )
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
    op.create_index("ix_user_subscriptions_tariff_id", "user_subscriptions", ["tariff_id"])


def downgrade() -> None:
    op.drop_index("ix_user_subscriptions_tariff_id", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")

    op.drop_index("ix_tariffs_code", table_name="tariffs")
    op.drop_table("tariffs")

    op.drop_index("ix_attempt_answers_task_id", table_name="attempt_answers")
    op.drop_index("ix_attempt_answers_attempt_id", table_name="attempt_answers")
    op.drop_table("attempt_answers")

    op.drop_index("ix_attempts_variant_id", table_name="attempts")
    op.drop_index("ix_attempts_user_id", table_name="attempts")
    op.drop_table("attempts")

    op.drop_index("ix_variant_tasks_task_id", table_name="variant_tasks")
    op.drop_index("ix_variant_tasks_variant_id", table_name="variant_tasks")
    op.drop_table("variant_tasks")

    op.drop_index("ix_variants_grade", table_name="variants")
    op.drop_index("ix_variants_exam_type", table_name="variants")
    op.drop_table("variants")

    op.drop_index("ix_task_options_task_id", table_name="task_options")
    op.drop_table("task_options")

    op.drop_index("ix_tasks_category_id", table_name="tasks")
    op.drop_index("ix_tasks_exam_type", table_name="tasks")
    op.drop_index("ix_tasks_grade", table_name="tasks")
    op.drop_table("tasks")

    op.drop_table("task_categories")

    op.drop_index("ix_theory_concepts_topic_id", table_name="theory_concepts")
    op.drop_table("theory_concepts")

    op.drop_index("ix_theory_topics_slug", table_name="theory_topics")
    op.drop_index("ix_theory_topics_grade", table_name="theory_topics")
    op.drop_table("theory_topics")

    op.drop_table("user_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
