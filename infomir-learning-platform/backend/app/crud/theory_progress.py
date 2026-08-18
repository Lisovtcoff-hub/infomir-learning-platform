from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.task import TaskCategory
from backend.app.models.theory import TheoryTopic, TheoryTopicProgress


def mark_topic_completed(db: Session, *, user_id: int, topic_id: int) -> TheoryTopicProgress | None:
    topic = db.execute(select(TheoryTopic).where(TheoryTopic.id == topic_id)).scalar_one_or_none()
    if not topic:
        return None

    existing = db.execute(
        select(TheoryTopicProgress).where(
            TheoryTopicProgress.user_id == user_id,
            TheoryTopicProgress.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    progress = TheoryTopicProgress(user_id=user_id, topic_id=topic_id)
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


def get_user_theory_progress_stats(
    db: Session,
    *,
    user_id: int,
    grade: int | None,
    max_sort_order: int | None = None,
) -> dict[str, int]:
    if grade is None:
        return {"completed_topics": 0, "total_topics": 0}

    total_stmt = (
        select(func.count(TheoryTopic.id))
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .where(TaskCategory.grade == grade)
    )
    if max_sort_order is not None:
        total_stmt = total_stmt.where(TaskCategory.sort_order <= max_sort_order)
    total_topics = db.execute(total_stmt).scalar_one()

    completed_stmt = (
        select(func.count(TheoryTopicProgress.id))
        .join(TheoryTopic, TheoryTopic.id == TheoryTopicProgress.topic_id)
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .where(
            TheoryTopicProgress.user_id == user_id,
            TaskCategory.grade == grade,
        )
    )
    if max_sort_order is not None:
        completed_stmt = completed_stmt.where(TaskCategory.sort_order <= max_sort_order)
    completed_topics = db.execute(completed_stmt).scalar_one()

    return {
        "completed_topics": int(completed_topics or 0),
        "total_topics": int(total_topics or 0),
    }


def get_user_completed_topic_ids(
    db: Session,
    *,
    user_id: int,
    grade: int | None,
    max_sort_order: int | None = None,
) -> list[int]:
    stmt = (
        select(TheoryTopicProgress.topic_id)
        .join(TheoryTopic, TheoryTopic.id == TheoryTopicProgress.topic_id)
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .where(TheoryTopicProgress.user_id == user_id)
        .order_by(TheoryTopicProgress.topic_id.asc())
    )
    if grade is not None:
        stmt = stmt.where(TaskCategory.grade == grade)
    if max_sort_order is not None:
        stmt = stmt.where(TaskCategory.sort_order <= max_sort_order)
    return [int(x) for x in db.execute(stmt).scalars().all()]


def reset_user_theory_progress(db: Session, *, user_id: int) -> int:
    rows = db.execute(
        select(TheoryTopicProgress).where(TheoryTopicProgress.user_id == user_id)
    ).scalars().all()
    count = len(rows)
    if not count:
        return 0
    for row in rows:
        db.delete(row)
    db.commit()
    return count
