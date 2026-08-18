from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_optional_current_user
from backend.app.core.entitlements import has_feature
from backend.app.crud.theory import get_topic_by_slug, get_topics
from backend.app.crud.theory_progress import (
    get_user_completed_topic_ids,
    get_user_theory_progress_stats,
    mark_topic_completed,
    reset_user_theory_progress,
)
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.theory import TheoryTopic
from backend.app.schemas.theory import TheoryProgressMarkResponse, TheoryProgressStatsRead, TheoryTopicRead

router = APIRouter(prefix="/theory", tags=["theory"])


@router.get("/", response_model=list[TheoryTopicRead])
def list_topics(
    grade: int | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    topics = get_topics(db, grade, subject)
    if not (current_user and has_feature(current_user, "theory_full")):
        topics = [topic for topic in topics if int(topic.category_sort_order or topic.sort_order or 0) <= 3]
    return [
        {
            "id": topic.id,
            "category_id": topic.category_id,
            "category_title": topic.category_title,
            "category_sort_order": topic.category_sort_order,
            "grade": topic.category_grade,
            "subject": topic.category_subject,
            "slug": topic.slug,
            "title": topic.category_title or "",
            "content_json": topic.content_json or [],
        }
        for topic in topics
    ]


@router.post("/progress/{topic_id}/complete", response_model=TheoryProgressMarkResponse)
def complete_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = db.get(TheoryTopic, topic_id)
    if topic and int(topic.category_sort_order or topic.sort_order or 0) > 3 and not has_feature(current_user, "theory_full"):
        raise HTTPException(status_code=402, detail="A tariff with full theory access is required")
    progress = mark_topic_completed(db, user_id=current_user.id, topic_id=topic_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"ok": True}


@router.get("/progress/my", response_model=TheoryProgressStatsRead)
def my_theory_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_theory_progress_stats(
        db,
        user_id=current_user.id,
        grade=current_user.grade,
        max_sort_order=None if has_feature(current_user, "theory_full") else 3,
    )


@router.get("/progress/my/topics", response_model=list[int])
def my_theory_completed_topics(
    grade: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_grade = grade if grade is not None else current_user.grade
    return get_user_completed_topic_ids(
        db,
        user_id=current_user.id,
        grade=effective_grade,
        max_sort_order=None if has_feature(current_user, "theory_full") else 3,
    )


@router.delete("/progress/my")
def reset_my_theory_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = reset_user_theory_progress(db, user_id=current_user.id)
    return {"ok": True, "deleted": deleted}


@router.get("/{grade}/{slug}", response_model=TheoryTopicRead)
def retrieve_topic(
    grade: int,
    slug: str,
    subject: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    topic = get_topic_by_slug(db, grade, slug, subject)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if int(topic.category_sort_order or topic.sort_order or 0) > 3 and not (
        current_user and has_feature(current_user, "theory_full")
    ):
        raise HTTPException(status_code=402, detail="A tariff with full theory access is required")
    return {
        "id": topic.id,
        "category_id": topic.category_id,
        "category_title": topic.category_title,
        "category_sort_order": topic.category_sort_order,
        "grade": topic.category_grade,
        "subject": topic.category_subject,
        "slug": topic.slug,
        "title": topic.category_title or "",
        "content_json": topic.content_json or [],
    }
