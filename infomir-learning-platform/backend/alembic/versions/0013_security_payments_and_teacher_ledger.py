"""security, payments, subscriptions and teacher ledger

Revision ID: 0013_security_payments_and_teacher_ledger
Revises: 0012_subjects_support
Create Date: 2026-08-09 16:00:00
"""

from __future__ import annotations

import secrets

from alembic import op
import sqlalchemy as sa


revision: str = "0013_security_payments_and_teacher_ledger"
down_revision: str | None = "0012_subjects_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    duplicate_answers = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT attempt_id, task_id FROM attempt_answers "
            "GROUP BY attempt_id, task_id HAVING COUNT(*) > 1)"
        )
    ).scalar_one()
    if duplicate_answers:
        raise RuntimeError("Cannot add attempt answer uniqueness: duplicate attempt/task rows exist")

    duplicate_students = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT student_id FROM teacher_group_members "
            "GROUP BY student_id HAVING COUNT(*) > 1)"
        )
    ).scalar_one()
    if duplicate_students:
        raise RuntimeError("Cannot enforce one teacher per student: duplicate memberships exist")

    duplicate_emails = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT lower(email) FROM users GROUP BY lower(email) HAVING COUNT(*) > 1)"
        )
    ).scalar_one()
    if duplicate_emails:
        raise RuntimeError("Cannot enable case-insensitive login: duplicate email addresses differ only by case")

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("paid_tariff_expires_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("tariffs") as batch_op:
        batch_op.add_column(
            sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30")
        )
        batch_op.create_check_constraint("ck_tariffs_price_nonnegative", "price >= 0")
        batch_op.create_check_constraint("ck_tariffs_duration_positive", "duration_days > 0")

    bind.execute(sa.text("UPDATE tariffs SET duration_days = 36500 WHERE code = 'free'"))

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_nonnegative"),
        sa.CheckConstraint(
            "status IN ('pending','paid','failed','refunded','cancelled')",
            name="ck_payments_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tariff_id"], ["tariffs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.UniqueConstraint("provider", "external_id", name="uq_payments_provider_external_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_tariff_id", "payments", ["tariff_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_external_id", "payments", ["external_id"], unique=False)

    with op.batch_alter_table("user_subscriptions") as batch_op:
        batch_op.add_column(sa.Column("payment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_user_subscriptions_payment_id_payments",
            "payments",
            ["payment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint("uq_user_subscriptions_payment_id", ["payment_id"])
        batch_op.create_index("ix_user_subscriptions_payment_id", ["payment_id"], unique=False)

    op.create_table(
        "teacher_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("invite_code", sa.String(16), nullable=False),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "commission_percent >= 0 AND commission_percent <= 100",
            name="ck_teacher_profiles_commission_percent",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("invite_code", name="uq_teacher_profiles_invite_code"),
    )
    op.create_index("ix_teacher_profiles_invite_code", "teacher_profiles", ["invite_code"], unique=True)

    teacher_ids = [int(row[0]) for row in bind.execute(sa.text("SELECT id FROM users WHERE role = 'teacher'"))]
    for teacher_id in teacher_ids:
        bind.execute(
            sa.text(
                "INSERT INTO teacher_profiles (user_id, invite_code, commission_percent) "
                "VALUES (:user_id, :invite_code, 20.00)"
            ),
            {"user_id": teacher_id, "invite_code": f"T-{secrets.token_hex(6).upper()}"},
        )

    op.create_table(
        "teacher_commissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_teacher_commissions_amount_nonnegative"),
        sa.CheckConstraint(
            "commission_percent >= 0 AND commission_percent <= 100",
            name="ck_teacher_commissions_percent",
        ),
        sa.CheckConstraint(
            "status IN ('available','reversed')",
            name="ck_teacher_commissions_status",
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_teacher_commissions_payment_id"),
    )
    op.create_index("ix_teacher_commissions_teacher_id", "teacher_commissions", ["teacher_id"], unique=False)
    op.create_index("ix_teacher_commissions_student_id", "teacher_commissions", ["student_id"], unique=False)
    op.create_index("ix_teacher_commissions_payment_id", "teacher_commissions", ["payment_id"], unique=True)
    op.create_index("ix_teacher_commissions_status", "teacher_commissions", ["status"], unique=False)

    with op.batch_alter_table("teacher_withdrawals") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("note", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    bind.execute(sa.text("UPDATE teacher_withdrawals SET status = 'paid', updated_at = created_at"))
    with op.batch_alter_table("teacher_withdrawals") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(20), nullable=False, server_default="requested")
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.create_check_constraint(
            "ck_teacher_withdrawals_status",
            "status IN ('requested','processing','paid','rejected')",
        )
        batch_op.create_check_constraint("ck_teacher_withdrawals_amount_positive", "amount > 0")
        batch_op.create_index("ix_teacher_withdrawals_status", ["status"], unique=False)

    with op.batch_alter_table("attempt_answers") as batch_op:
        batch_op.create_unique_constraint(
            "uq_attempt_answers_attempt_task",
            ["attempt_id", "task_id"],
        )
    with op.batch_alter_table("teacher_group_members") as batch_op:
        batch_op.create_unique_constraint(
            "uq_teacher_group_members_student_id",
            ["student_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("teacher_group_members") as batch_op:
        batch_op.drop_constraint("uq_teacher_group_members_student_id", type_="unique")
    with op.batch_alter_table("attempt_answers") as batch_op:
        batch_op.drop_constraint("uq_attempt_answers_attempt_task", type_="unique")

    with op.batch_alter_table("teacher_withdrawals") as batch_op:
        batch_op.drop_index("ix_teacher_withdrawals_status")
        batch_op.drop_constraint("ck_teacher_withdrawals_amount_positive", type_="check")
        batch_op.drop_constraint("ck_teacher_withdrawals_status", type_="check")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("note")
        batch_op.drop_column("status")

    op.drop_index("ix_teacher_commissions_status", table_name="teacher_commissions")
    op.drop_index("ix_teacher_commissions_payment_id", table_name="teacher_commissions")
    op.drop_index("ix_teacher_commissions_student_id", table_name="teacher_commissions")
    op.drop_index("ix_teacher_commissions_teacher_id", table_name="teacher_commissions")
    op.drop_table("teacher_commissions")
    op.drop_index("ix_teacher_profiles_invite_code", table_name="teacher_profiles")
    op.drop_table("teacher_profiles")

    with op.batch_alter_table("user_subscriptions") as batch_op:
        batch_op.drop_index("ix_user_subscriptions_payment_id")
        batch_op.drop_constraint("uq_user_subscriptions_payment_id", type_="unique")
        batch_op.drop_constraint("fk_user_subscriptions_payment_id_payments", type_="foreignkey")
        batch_op.drop_column("payment_id")

    op.drop_index("ix_payments_external_id", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_tariff_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")

    with op.batch_alter_table("tariffs") as batch_op:
        batch_op.drop_constraint("ck_tariffs_duration_positive", type_="check")
        batch_op.drop_constraint("ck_tariffs_price_nonnegative", type_="check")
        batch_op.drop_column("duration_days")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("paid_tariff_expires_at")
