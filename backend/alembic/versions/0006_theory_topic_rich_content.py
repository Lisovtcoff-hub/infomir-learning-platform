"""migrate theory topics to rich content json

Revision ID: 0006_theory_topic_rich_content
Revises: 0005_drop_grade_title_from_theory_topics
Create Date: 2026-05-06
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision: str = "0006_theory_topic_rich_content"
down_revision: str | None = "0005_drop_grade_title_from_theory_topics"
branch_labels = None
depends_on = None


def _build_content_json(text: str | None, example: str | None, tip: str | None) -> str:
    blocks: list[dict] = []
    if text and text.strip():
        blocks.append({"type": "paragraph", "text": text.strip()})
    if example and example.strip():
        blocks.append({"type": "heading", "level": 3, "text": "Пример"})
        blocks.append({"type": "paragraph", "text": example.strip()})
    if tip and tip.strip():
        blocks.append({"type": "callout", "variant": "gray", "title": "Совет", "text": tip.strip()})
    return json.dumps(blocks, ensure_ascii=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("theory_topics")}

    if "content_json" not in columns:
        op.add_column("theory_topics", sa.Column("content_json", sa.JSON(), nullable=True))

    rows = bind.execute(sa.text("SELECT id, text, example, tip FROM theory_topics")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE theory_topics SET content_json = :content WHERE id = :topic_id"),
            {"content": _build_content_json(row.text, row.example, row.tip), "topic_id": row.id},
        )

    with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
        batch_op.alter_column("content_json", nullable=False)
        batch_op.drop_column("text")
        batch_op.drop_column("example")
        batch_op.drop_column("tip")

    if "theory_concepts" in inspector.get_table_names():
        op.drop_table("theory_concepts")


def downgrade() -> None:
    with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("text", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("example", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("tip", sa.Text(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, content_json FROM theory_topics")).fetchall()
    for row in rows:
        text = ""
        example = None
        tip = None
        try:
            blocks = row.content_json or []
        except Exception:
            blocks = []
        if isinstance(blocks, str):
            try:
                blocks = json.loads(blocks)
            except Exception:
                blocks = []

        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "paragraph" and not text:
                    text = str(block.get("text") or "")
                elif block_type == "callout" and not tip:
                    tip = str(block.get("text") or "")
                elif block_type == "paragraph" and text and not example:
                    example = str(block.get("text") or "")

        bind.execute(
            sa.text("UPDATE theory_topics SET text = :text, example = :example, tip = :tip WHERE id = :topic_id"),
            {"text": text, "example": example, "tip": tip, "topic_id": row.id},
        )

    with op.batch_alter_table("theory_topics", recreate="always") as batch_op:
        batch_op.drop_column("content_json")

    op.create_table(
        "theory_concepts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("theory_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_theory_concepts_topic_id", "theory_concepts", ["topic_id"])
