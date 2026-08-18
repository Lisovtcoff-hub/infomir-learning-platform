"""add student access code

Revision ID: 0010_student_access_code
Revises: 0009_teacher_invites
Create Date: 2026-05-09 11:50:00
"""

from __future__ import annotations

import random

from alembic import op
import sqlalchemy as sa


revision: str = "0010_student_access_code"
down_revision: str | None = "0009_teacher_invites"
branch_labels = None
depends_on = None


def _generate_code() -> str:
    return f"{random.randint(0, 9999):04d}"


def upgrade() -> None:
    op.add_column("users", sa.Column("student_access_code", sa.String(length=4), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM users")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE users SET student_access_code = :code WHERE id = :id"),
            {"id": int(row.id), "code": _generate_code()},
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("student_access_code", existing_type=sa.String(length=4), nullable=False, server_default="0000")
        batch_op.create_check_constraint("ck_users_student_access_code_4_digits", "length(student_access_code) = 4")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_student_access_code_4_digits", type_="check")
        batch_op.drop_column("student_access_code")
