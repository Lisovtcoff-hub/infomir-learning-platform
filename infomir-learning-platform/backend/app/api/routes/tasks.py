from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import Request

from backend.app.api.deps import get_current_user, get_optional_current_user
from backend.app.core.entitlements import has_feature
from backend.app.core.rate_limit import client_key, rate_limiter
from backend.app.crud.task import check_answer, get_task, get_task_categories, get_tasks
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.task import TaskCategoryRead, TaskCheckRequest, TaskCheckResponse, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=list[TaskRead])
def list_tasks(
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
    category_id: int | None = None,
    difficulty: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    full_access = bool(current_user and has_feature(current_user, "practice_full"))
    if not full_access and difficulty and difficulty.strip().lower() != "easy":
        raise HTTPException(status_code=402, detail="A tariff with full practice access is required")
    effective_difficulty = difficulty if full_access else "easy"
    return get_tasks(db, grade=grade, exam_type=exam_type, subject=subject, category_id=category_id, difficulty=effective_difficulty)


@router.get("/categories", response_model=list[TaskCategoryRead])
def list_task_categories(
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
):
    return get_task_categories(db, grade=grade, exam_type=exam_type, subject=subject)


@router.get("/{task_id}", response_model=TaskRead)
def retrieve_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if str(task.difficulty or "medium").lower() != "easy" and not (
        current_user and has_feature(current_user, "practice_full")
    ):
        raise HTTPException(status_code=402, detail="A tariff with full practice access is required")
    return task


@router.post("/{task_id}/check", response_model=TaskCheckResponse)
def check_task(
    task_id: int,
    payload: TaskCheckRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limiter.check(client_key(request, "task-check", str(current_user.id)), limit=120, window_seconds=60)
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not has_feature(current_user, "practice_basic"):
        raise HTTPException(status_code=402, detail="A tariff with practice access is required")
    if str(task.difficulty or "medium").lower() != "easy" and not has_feature(current_user, "practice_full"):
        raise HTTPException(status_code=402, detail="A tariff with full practice access is required")
    if current_user.grade is not None and task.grade is not None and int(current_user.grade) != int(task.grade):
        raise HTTPException(status_code=403, detail="Task does not match the student's grade")
    is_correct = check_answer(db, task_id, payload.user_answer)
    return TaskCheckResponse(
        task_id=task_id,
        is_correct=is_correct,
        correct_answer=task.answer,
        explanation=task.explanation,
    )
