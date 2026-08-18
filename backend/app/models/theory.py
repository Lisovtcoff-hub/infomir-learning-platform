from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class TheoryTopic(Base):
    __tablename__ = "theory_topics"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_theory_topics_slug"),
        UniqueConstraint("category_id", name="uq_theory_topics_category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category = relationship("TaskCategory", back_populates="theory_topics", lazy="joined")

    @property
    def category_title(self) -> str | None:
        return self.category.title if self.category else None

    @property
    def category_sort_order(self) -> int | None:
        return self.category.sort_order if self.category else None

    @property
    def category_grade(self) -> int | None:
        return self.category.grade if self.category else None

    @property
    def category_subject(self) -> str | None:
        return self.category.subject if self.category else None


class TheoryTopicProgress(Base):
    __tablename__ = "theory_topic_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_theory_topic_progress_user_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("theory_topics.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
