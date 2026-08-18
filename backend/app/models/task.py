from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class TaskCategory(Base):
    __tablename__ = "task_categories"
    __table_args__ = (
        UniqueConstraint("code", "grade", "exam_type", "subject", name="uq_task_categories_code_grade_exam_subject"),
        UniqueConstraint("title", "grade", "exam_type", "subject", name="uq_task_categories_title_grade_exam_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, default="informatics")
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tasks: Mapped[list["Task"]] = relationship(back_populates="category")
    theory_topics = relationship("TheoryTopic", back_populates="category")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("task_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    exam_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, default="informatics", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    category: Mapped[TaskCategory | None] = relationship(back_populates="tasks")
    options: Mapped[list["TaskOption"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    @property
    def category_title(self) -> str | None:
        return self.category.title if self.category else None

    @property
    def category_sort_order(self) -> int | None:
        return self.category.sort_order if self.category else None


class TaskOption(Base):
    __tablename__ = "task_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    task: Mapped[Task] = relationship(back_populates="options")
