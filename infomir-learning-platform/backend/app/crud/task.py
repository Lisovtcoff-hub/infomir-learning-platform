from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.task import Task, TaskCategory


def get_tasks(
    db: Session,
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
    category_id: int | None = None,
    difficulty: str | None = None,
) -> list[Task]:
    stmt = select(Task).options(selectinload(Task.options), selectinload(Task.category)).order_by(Task.id)
    if grade is not None:
        stmt = stmt.where(Task.grade == grade)
    if exam_type is not None:
        stmt = stmt.where(Task.exam_type == exam_type)
    if subject is not None:
        stmt = stmt.where(Task.subject == subject)
    if category_id is not None:
        stmt = stmt.where(Task.category_id == category_id)
    if difficulty is not None:
        stmt = stmt.where(Task.difficulty == difficulty)
    return list(db.execute(stmt.limit(1000)).scalars().all())


def get_task(db: Session, task_id: int) -> Task | None:
    stmt = select(Task).options(selectinload(Task.options), selectinload(Task.category)).where(Task.id == task_id)
    return db.execute(stmt).scalar_one_or_none()


def get_task_categories(
    db: Session,
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
) -> list[TaskCategory]:
    stmt = select(TaskCategory).order_by(TaskCategory.sort_order.asc(), TaskCategory.id.asc())
    if grade is not None:
        stmt = stmt.where(TaskCategory.grade == grade)
    if exam_type is not None:
        stmt = stmt.where(TaskCategory.exam_type == exam_type)
    if subject is not None:
        stmt = stmt.where(TaskCategory.subject == subject)
    return list(db.execute(stmt.limit(500)).scalars().all())


def check_answer(db: Session, task_id: int, user_answer: str) -> bool:
    task = get_task(db, task_id)
    if not task:
        return False
    return task.answer.strip().lower() == user_answer.strip().lower()
