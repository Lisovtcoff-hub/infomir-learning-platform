from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.variant import Variant


def get_variants(
    db: Session,
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
) -> list[Variant]:
    stmt = select(Variant).order_by(Variant.id)
    if grade is not None:
        stmt = stmt.where(Variant.grade == grade)
    if exam_type is not None:
        stmt = stmt.where(Variant.exam_type == exam_type)
    if subject is not None:
        stmt = stmt.where(Variant.subject == subject)
    return list(db.execute(stmt.limit(300)).scalars().all())


def get_variant_with_tasks(db: Session, variant_id: int) -> Variant | None:
    stmt = select(Variant).options(selectinload(Variant.variant_tasks)).where(Variant.id == variant_id)
    return db.execute(stmt).scalar_one_or_none()
