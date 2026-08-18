"""production hardening

Revision ID: 0016_production_hardening
Revises: 0015_drop_student_access_code
Create Date: 2026-08-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0016_production_hardening"
down_revision: str | None = "0015_drop_student_access_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    invalid_attempts = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM attempts WHERE "
            "(mode = 'practice' AND variant_id IS NOT NULL) OR "
            "(mode = 'variant' AND variant_id IS NULL) OR "
            "mode NOT IN ('practice', 'variant')"
        )
    ).scalar_one()
    if invalid_attempts:
        raise RuntimeError("Invalid attempt mode/variant rows must be corrected before upgrading")

    active_duplicates = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT teacher_id FROM teacher_withdrawals "
            "WHERE status IN ('requested','processing') GROUP BY teacher_id HAVING COUNT(*) > 1) AS duplicates"
        )
    ).scalar_one()
    if active_duplicates:
        raise RuntimeError("Duplicate active teacher withdrawals must be resolved before upgrading")

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("attempts") as batch_op:
        batch_op.create_check_constraint(
            "ck_attempts_mode_variant",
            "(mode = 'practice' AND variant_id IS NULL) OR (mode = 'variant' AND variant_id IS NOT NULL)",
        )

    theory_foreign_keys = sa.inspect(bind).get_foreign_keys("theory_topics")
    if not any(
        item.get("referred_table") == "task_categories" and item.get("constrained_columns") == ["category_id"]
        for item in theory_foreign_keys
    ):
        with op.batch_alter_table("theory_topics") as batch_op:
            batch_op.create_foreign_key(
                "fk_theory_topics_category_id_task_categories",
                "task_categories",
                ["category_id"],
                ["id"],
                ondelete="SET NULL",
            )

    active_predicate = sa.text("status IN ('requested','processing')")
    op.create_index(
        "uq_teacher_withdrawals_one_active",
        "teacher_withdrawals",
        ["teacher_id"],
        unique=True,
        postgresql_where=active_predicate,
        sqlite_where=active_predicate,
    )
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_index("uq_teacher_withdrawals_one_active", table_name="teacher_withdrawals")
    with op.batch_alter_table("attempts") as batch_op:
        batch_op.drop_constraint("ck_attempts_mode_variant", type_="check")
    theory_foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("theory_topics")
    if any(item.get("name") == "fk_theory_topics_category_id_task_categories" for item in theory_foreign_keys):
        with op.batch_alter_table("theory_topics") as batch_op:
            batch_op.drop_constraint("fk_theory_topics_category_id_task_categories", type_="foreignkey")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("session_version")
