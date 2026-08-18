"""add task hints

Revision ID: 0014_task_hints
Revises: 0013_security_payments_and_teacher_ledger
Create Date: 2026-08-09 17:00:00
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0014_task_hints"
down_revision: str | None = "0013_security_payments_and_teacher_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("hint", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("hint")
