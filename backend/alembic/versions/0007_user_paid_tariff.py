"""add current paid tariff to users

Revision ID: 0007_user_paid_tariff
Revises: 0006_theory_topic_rich_content
Create Date: 2026-05-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0007_user_paid_tariff"
down_revision: str | None = "0006_theory_topic_rich_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {col["name"] for col in inspector.get_columns("users")}

    if "paid_tariff_id" not in user_columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("users", recreate="always") as batch_op:
                batch_op.add_column(sa.Column("paid_tariff_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_users_paid_tariff_id_tariffs",
                    "tariffs",
                    ["paid_tariff_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch_op.create_index(
                    "ix_users_paid_tariff_id",
                    ["paid_tariff_id"],
                    unique=False,
                )
        else:
            op.add_column(
                "users",
                sa.Column("paid_tariff_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_users_paid_tariff_id_tariffs",
                "users",
                "tariffs",
                ["paid_tariff_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index(
                "ix_users_paid_tariff_id",
                "users",
                ["paid_tariff_id"],
                unique=False,
            )

    free_tariff_id = bind.execute(sa.text("SELECT id FROM tariffs WHERE code = 'free' LIMIT 1")).scalar_one_or_none()
    if free_tariff_id is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO tariffs (code, title, price, description, features_json, is_active)
                VALUES (:code, :title, :price, :description, :features_json, :is_active)
                """
            ),
            {
                "code": "free",
                "title": "Бесплатный",
                "price": 0,
                "description": "Базовый доступ",
                "features_json": '["Базовый доступ"]',
                "is_active": 1,
            },
        )
        free_tariff_id = bind.execute(sa.text("SELECT id FROM tariffs WHERE code = 'free' LIMIT 1")).scalar_one()

    bind.execute(
        sa.text(
            """
            UPDATE users
            SET paid_tariff_id = :free_tariff_id
            WHERE paid_tariff_id IS NULL
            """
        ),
        {"free_tariff_id": int(free_tariff_id)},
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "paid_tariff_id" not in user_columns:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_index("ix_users_paid_tariff_id")
            batch_op.drop_constraint(
                "fk_users_paid_tariff_id_tariffs",
                type_="foreignkey",
            )
            batch_op.drop_column("paid_tariff_id")
        return

    op.drop_index("ix_users_paid_tariff_id", table_name="users")
    op.drop_constraint(
        "fk_users_paid_tariff_id_tariffs",
        "users",
        type_="foreignkey",
    )
    op.drop_column("users", "paid_tariff_id")
