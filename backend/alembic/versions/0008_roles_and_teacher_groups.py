"""add role constraint and teacher groups

Revision ID: 0008_roles_and_teacher_groups
Revises: 0007_user_paid_tariff
Create Date: 2026-05-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_roles_and_teacher_groups"
down_revision: str | None = "0007_user_paid_tariff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_CHECK_NAME = "ck_users_role_allowed"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET role = 'student' "
            "WHERE role IS NULL OR lower(trim(role)) NOT IN ('student', 'teacher', 'admin')"
        )
    )
    op.execute(sa.text("UPDATE users SET role = lower(trim(role))"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role", existing_type=sa.String(length=50), server_default="student", nullable=False)
        batch_op.create_check_constraint(ROLE_CHECK_NAME, "role IN ('student', 'teacher', 'admin')")

    op.create_table(
        "teacher_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("teacher_id", "title", name="uq_teacher_groups_teacher_id_title"),
    )
    op.create_index("ix_teacher_groups_teacher_id", "teacher_groups", ["teacher_id"])

    op.create_table(
        "teacher_group_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("teacher_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("group_id", "student_id", name="uq_teacher_group_members_group_id_student_id"),
    )
    op.create_index("ix_teacher_group_members_group_id", "teacher_group_members", ["group_id"])
    op.create_index("ix_teacher_group_members_student_id", "teacher_group_members", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_teacher_group_members_student_id", table_name="teacher_group_members")
    op.drop_index("ix_teacher_group_members_group_id", table_name="teacher_group_members")
    op.drop_table("teacher_group_members")

    op.drop_index("ix_teacher_groups_teacher_id", table_name="teacher_groups")
    op.drop_table("teacher_groups")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(ROLE_CHECK_NAME, type_="check")
        batch_op.alter_column("role", existing_type=sa.String(length=50), server_default=None, nullable=False)

