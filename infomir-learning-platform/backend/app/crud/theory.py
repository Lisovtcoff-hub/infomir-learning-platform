from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.task import TaskCategory
from backend.app.models.theory import TheoryTopic


def get_topics(db: Session, grade: int | None = None, subject: str | None = None) -> list[TheoryTopic]:
    stmt = (
        select(TheoryTopic)
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .order_by(TaskCategory.grade, TaskCategory.sort_order, TheoryTopic.sort_order, TheoryTopic.id)
    )
    if grade is not None:
        stmt = stmt.where(TaskCategory.grade == grade)
    if subject is not None:
        stmt = stmt.where(TaskCategory.subject == subject)
    return list(db.execute(stmt).scalars().all())


def get_topic_by_slug(db: Session, grade: int, slug: str, subject: str | None = None) -> TheoryTopic | None:
    stmt = (
        select(TheoryTopic)
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .where(TaskCategory.grade == grade, TheoryTopic.slug == slug)
    )
    if subject is not None:
        stmt = stmt.where(TaskCategory.subject == subject)
    return db.execute(stmt).scalar_one_or_none()


def create_or_update_topic(
    db: Session,
    *,
    slug: str,
    content_json: list[dict],
    sort_order: int = 0,
    category_id: int | None = None,
) -> TheoryTopic:
    topic = db.execute(select(TheoryTopic).where(TheoryTopic.slug == slug)).scalar_one_or_none()
    if not topic:
        topic = TheoryTopic(
            slug=slug,
            content_json=content_json,
            sort_order=sort_order,
            category_id=category_id,
        )
        db.add(topic)
        db.flush()
    else:
        topic.content_json = content_json
        topic.sort_order = sort_order
        topic.category_id = category_id

    db.commit()
    db.refresh(topic)
    return topic
