from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.crud.attempt import (
    create_attempt,
    finish_attempt,
    get_attempt_result,
    get_attempt_stats_for_user,
    get_attempts_for_user,
    get_recommended_topics_for_user,
    get_week_activity_for_user,
    save_attempt_answer,
)
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.attempt import (
    AttemptAnswerCreate,
    AttemptAnswerAccepted,
    AttemptCreate,
    AttemptRead,
    AttemptResultRead,
    AttemptStatsRead,
    RecommendedTopicsRead,
    WeekActivityRead,
)

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("/", response_model=AttemptRead)
def start_attempt(
    payload: AttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return create_attempt(db, user_id=current_user.id, mode=payload.mode, variant_id=payload.variant_id)
    except PermissionError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{attempt_id}/answers", response_model=AttemptAnswerAccepted)
def add_answer(
    attempt_id: int,
    payload: AttemptAnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        answer = save_attempt_answer(
            db,
            user_id=current_user.id,
            attempt_id=attempt_id,
            task_id=payload.task_id,
            user_answer=payload.user_answer,
        )
        return AttemptAnswerAccepted(task_id=answer.task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{attempt_id}/finish", response_model=AttemptRead)
def complete_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = finish_attempt(db, user_id=current_user.id, attempt_id=attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


@router.get("/{attempt_id}/result", response_model=AttemptResultRead)
def attempt_result(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = get_attempt_result(db, user_id=current_user.id, attempt_id=attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return result


@router.get("/my", response_model=list[AttemptRead])
def my_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_attempts_for_user(db, current_user.id, current_user.grade)


@router.get("/my/stats", response_model=AttemptStatsRead)
def my_attempts_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_attempt_stats_for_user(db, current_user.id, current_user.grade)


@router.get("/my/activity-week", response_model=WeekActivityRead)
def my_week_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_week_activity_for_user(db, current_user.id, current_user.grade)


@router.get("/my/recommended-topics", response_model=RecommendedTopicsRead)
def my_recommended_topics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_recommended_topics_for_user(
        db,
        user_id=current_user.id,
        grade=current_user.grade,
        limit=3,
    )
