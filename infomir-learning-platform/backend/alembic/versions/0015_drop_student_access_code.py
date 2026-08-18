"""drop obsolete student access code

Revision ID: 0015_drop_student_access_code
Revises: 0014_task_hints
Create Date: 2026-08-09 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0015_drop_student_access_code"
down_revision: str | None = "0014_task_hints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_student_access_code_4_digits", type_="check")
        batch_op.drop_column("student_access_code")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("student_access_code", sa.String(length=4), nullable=False, server_default="0000")
        )
        batch_op.create_check_constraint(
            "ck_users_student_access_code_4_digits",
            "length(student_access_code) = 4",
        )
