from datetime import datetime, timedelta

from datetime import timezone

from sqlalchemy import case, func, select, exists, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.crud.task import check_answer
from backend.app.models.attempt import Attempt, AttemptAnswer
from backend.app.models.task import TaskCategory
from backend.app.models.task import Task
from backend.app.models.theory import TheoryTopic, TheoryTopicProgress
from backend.app.models.user import User
from backend.app.models.variant import Variant, VariantTask
from backend.app.core.entitlements import has_feature


def _utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_aware() -> datetime:
    return datetime.now(timezone.utc)


def _exam_type_for_grade(grade: int | None) -> str | None:
    if grade in (7, 8):
        return "vpr"
    if grade == 9:
        return "oge"
    return None


def _legacy_finished_attempt_ids_stmt(user_id: int):
    has_answers = exists(select(1).where(AttemptAnswer.attempt_id == Attempt.id))
    return (
        select(Attempt.id)
        .where(
            Attempt.user_id == user_id,
            Attempt.finished_at.is_not(None),
            Attempt.max_score > 0,
            ~has_answers,
            or_(
                func.lower(Attempt.mode).like("%variant%"),
                func.lower(Attempt.mode).like("%practice_seed%"),
            ),
        )
    )


def create_attempt(db: Session, user_id: int, mode: str, variant_id: int | None = None) -> Attempt:
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in {"practice", "variant"}:
        raise ValueError("Unsupported attempt mode")
    if normalized_mode == "variant" and variant_id is None:
        raise ValueError("variant_id is required for variant attempts")
    if normalized_mode == "practice" and variant_id is not None:
        raise ValueError("variant_id is not allowed for practice attempts")
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    if normalized_mode == "variant" and not has_feature(user, "variants"):
        raise PermissionError("A tariff with exam variants is required")
    if variant_id is not None:
        variant = db.get(Variant, variant_id)
        if not variant:
            raise ValueError("Variant not found")
        if user.grade is not None and variant.grade is not None and int(user.grade) != int(variant.grade):
            raise ValueError("Variant does not match the student's grade")
    attempt = Attempt(user_id=user_id, mode=normalized_mode, variant_id=variant_id, started_at=_utc_naive())
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def save_attempt_answer(
    db: Session,
    *,
    user_id: int,
    attempt_id: int,
    task_id: int,
    user_answer: str,
) -> AttemptAnswer:
    attempt = db.execute(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not attempt:
        raise LookupError("Attempt not found")
    if attempt.finished_at is not None:
        raise ValueError("Finished attempts cannot be changed")
    if attempt.variant_id is not None:
        variant = db.get(Variant, attempt.variant_id)
        if not variant:
            raise ValueError("Variant is unavailable")
        if variant.time_limit_minutes and _utc_naive() > attempt.started_at + timedelta(minutes=variant.time_limit_minutes):
            raise ValueError("The variant time limit has expired")

    task = db.get(Task, task_id)
    if not task:
        raise LookupError("Task not found")
    user = db.get(User, user_id)
    if user and user.grade is not None and task.grade is not None and int(user.grade) != int(task.grade):
        raise ValueError("Task does not match the student's grade")
    if attempt.variant_id is None and user and str(task.difficulty or "medium").lower() != "easy" and not has_feature(user, "practice_full"):
        raise PermissionError("A tariff with full practice access is required")
    if attempt.variant_id is not None:
        included = db.execute(
            select(VariantTask.id).where(
                VariantTask.variant_id == attempt.variant_id,
                VariantTask.task_id == task_id,
            )
        ).scalar_one_or_none()
        if included is None:
            raise ValueError("Task is not included in this variant")

    is_correct = check_answer(db, task_id, user_answer)
    answer = db.execute(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.task_id == task_id)
    ).scalar_one_or_none()

    if not answer:
        answer = AttemptAnswer(
            attempt_id=attempt_id,
            task_id=task_id,
            user_answer=user_answer,
            is_correct=is_correct,
            points_earned=1 if is_correct else 0,
            checked_at=_utc_aware(),
        )
        db.add(answer)
    else:
        answer.user_answer = user_answer
        answer.is_correct = is_correct
        answer.points_earned = 1 if is_correct else 0
        answer.checked_at = _utc_aware()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        answer = db.execute(
            select(AttemptAnswer).where(
                AttemptAnswer.attempt_id == attempt_id,
                AttemptAnswer.task_id == task_id,
            )
        ).scalar_one()
        answer.user_answer = user_answer
        answer.is_correct = is_correct
        answer.points_earned = 1 if is_correct else 0
        answer.checked_at = _utc_aware()
        db.commit()
    db.refresh(answer)
    return answer


def finish_attempt(db: Session, *, user_id: int, attempt_id: int) -> Attempt | None:
    attempt = db.execute(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not attempt:
        return None
    if attempt.finished_at is not None:
        return attempt

    answers = list(db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)).scalars().all())
    if attempt.variant_id is not None:
        max_score = int(
            db.execute(
                select(func.coalesce(func.sum(VariantTask.points), 0)).where(
                    VariantTask.variant_id == attempt.variant_id
                )
            ).scalar_one()
            or 0
        )
    else:
        max_score = len(answers)
    score = sum(item.points_earned for item in answers)
    percent = int((score / max_score) * 100) if max_score else 0

    attempt.finished_at = _utc_naive()
    attempt.score = score
    attempt.max_score = max_score
    attempt.percent = percent
    if percent < 40:
        attempt.grade_mark = 2
    elif percent < 60:
        attempt.grade_mark = 3
    elif percent < 85:
        attempt.grade_mark = 4
    else:
        attempt.grade_mark = 5

    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_attempt_result(db: Session, *, user_id: int, attempt_id: int) -> dict | None:
    attempt = db.execute(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user_id)
    ).scalar_one_or_none()
    if not attempt:
        return None
    if attempt.finished_at is None:
        raise ValueError("Attempt must be finished before solutions are available")

    answers = {
        row.task_id: row
        for row in db.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
        ).scalars().all()
    }
    if attempt.variant_id is not None:
        task_ids = list(
            db.execute(
                select(VariantTask.task_id)
                .where(VariantTask.variant_id == attempt.variant_id)
                .order_by(VariantTask.sort_order.asc(), VariantTask.id.asc())
            ).scalars().all()
        )
    else:
        task_ids = list(answers)

    tasks = {
        task.id: task
        for task in db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()
    } if task_ids else {}
    result = []
    for task_id in task_ids:
        task = tasks.get(task_id)
        if not task:
            continue
        answer = answers.get(task_id)
        result.append({
            "task_id": task_id,
            "user_answer": answer.user_answer if answer else None,
            "is_correct": bool(answer and answer.is_correct),
            "correct_answer": task.answer,
            "explanation": task.explanation,
        })
    return {"attempt_id": attempt.id, "answers": result}


def get_attempts_for_user(db: Session, user_id: int, grade: int | None = None) -> list[Attempt]:
    stmt = select(Attempt).options(selectinload(Attempt.variant)).where(Attempt.user_id == user_id)
    exam_type = _exam_type_for_grade(grade)
    if grade is not None:
        matched_attempt_ids = (
            select(AttemptAnswer.attempt_id)
            .join(Task, Task.id == AttemptAnswer.task_id)
            .where(Task.grade == grade)
        )
        if exam_type is not None:
            matched_attempt_ids = matched_attempt_ids.where(func.lower(Task.exam_type) == exam_type)
        matched_attempt_ids = matched_attempt_ids.distinct()
        # Keep historical finished attempts that have computed scores but no persisted AttemptAnswer rows.
        # We treat them as legacy snapshots so progress/grade metrics remain stable after schema changes.
        legacy_finished_stmt = _legacy_finished_attempt_ids_stmt(user_id)
        stmt = stmt.where(or_(Attempt.id.in_(matched_attempt_ids), Attempt.id.in_(legacy_finished_stmt)))
    stmt = stmt.order_by(Attempt.id.desc())
    return list(db.execute(stmt).scalars().all())


def get_attempt_stats_for_user(db: Session, user_id: int, grade: int | None = None) -> dict[str, int | float]:
    attempts = get_attempts_for_user(db, user_id, grade)
    attempts_total = len(attempts)
    finished_attempts = [item for item in attempts if item.finished_at is not None and int(item.max_score or 0) > 0]
    variant_attempts = [item for item in finished_attempts if "variant" in str(item.mode or "").lower()]
    recent_variant_attempts = variant_attempts[:5]

    solved_stmt = (
        select(func.count(func.distinct(AttemptAnswer.task_id)))
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(
            Attempt.user_id == user_id,
            AttemptAnswer.is_correct.is_(True),
        )
    )
    exam_type = _exam_type_for_grade(grade)
    if grade is not None:
        solved_stmt = solved_stmt.where(Task.grade == grade)
    if exam_type is not None:
        solved_stmt = solved_stmt.where(func.lower(Task.exam_type) == exam_type)
    solved_tasks_total = int(db.execute(solved_stmt).scalar_one() or 0)

    if finished_attempts:
        average_percent = round(sum(int(item.percent or 0) for item in finished_attempts) / len(finished_attempts))
        grades = [int(item.grade_mark) for item in finished_attempts if item.grade_mark is not None]
        average_grade = round(sum(grades) / len(grades), 1) if grades else 0.0
    else:
        average_percent = 0
        average_grade = 0.0

    if recent_variant_attempts:
        variant_average_percent = round(
            sum(int(item.percent or 0) for item in recent_variant_attempts) / len(recent_variant_attempts)
        )
        variant_grades = [int(item.grade_mark) for item in recent_variant_attempts if item.grade_mark is not None]
        predicted_exam_grade = round(sum(variant_grades) / len(variant_grades), 1) if variant_grades else 0.0
    else:
        variant_average_percent = 0
        predicted_exam_grade = 0.0

    # Fallback: if there are finished attempts but no "variant"-mode rows,
    # still provide a meaningful grade forecast from recent completed attempts.
    if predicted_exam_grade == 0.0 and finished_attempts:
        recent_finished = finished_attempts[:5]
        finished_grades = [int(item.grade_mark) for item in recent_finished if item.grade_mark is not None]
        if finished_grades:
            predicted_exam_grade = round(sum(finished_grades) / len(finished_grades), 1)

    recent_stability_attempts = variant_attempts[:3]
    stable_variants_count = sum(1 for item in recent_stability_attempts if int(item.percent or 0) >= 60)
    variant_stability_percent = (
        round((stable_variants_count / len(recent_stability_attempts)) * 100) if recent_stability_attempts else 0
    )

    total_topics = 0
    completed_topics = 0
    if grade is not None:
        progress_user = db.get(User, user_id)
        max_sort_order = None if progress_user and has_feature(progress_user, "theory_full") else 3
        total_stmt = (
            select(func.count(TheoryTopic.id))
            .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
            .where(TaskCategory.grade == grade)
        )
        completed_stmt = (
            select(func.count(TheoryTopicProgress.id))
            .join(TheoryTopic, TheoryTopic.id == TheoryTopicProgress.topic_id)
            .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
            .where(TheoryTopicProgress.user_id == user_id, TaskCategory.grade == grade)
        )
        if max_sort_order is not None:
            total_stmt = total_stmt.where(TaskCategory.sort_order <= max_sort_order)
            completed_stmt = completed_stmt.where(TaskCategory.sort_order <= max_sort_order)
        total_topics = int(
            db.execute(total_stmt).scalar_one()
            or 0
        )
        completed_topics = int(
            db.execute(completed_stmt).scalar_one()
            or 0
        )
    theory_completion_percent = round((completed_topics / total_topics) * 100) if total_topics else 0

    readiness_vpr = round(
        (variant_average_percent * 0.6) + (theory_completion_percent * 0.3) + (variant_stability_percent * 0.1)
    )

    return {
        "attempts_total": attempts_total,
        "solved_tasks_total": solved_tasks_total,
        "average_percent": average_percent,
        "average_grade": average_grade,
        "variant_average_percent": variant_average_percent,
        "predicted_exam_grade": predicted_exam_grade,
        "theory_completion_percent": theory_completion_percent,
        "variant_stability_percent": variant_stability_percent,
        "readiness_vpr_percent": readiness_vpr,
    }


def get_leaderboard_for_user(
    db: Session,
    *,
    current_user_id: int,
    top_limit: int = 5,
) -> dict[str, dict[str, int | float | list[dict[str, int | float | str | None]]]]:
    students = list(
        db.execute(
            select(User)
            .where(User.role == "student", User.is_active.is_(True))
            .order_by(User.id.asc())
        ).scalars().all()
    )
    total_students = len(students)
    if total_students == 0:
        empty = {
            "total_students": 0,
            "current_user_rank": 1,
            "current_user_rating": 0.0,
            "top": [],
        }
        return {"overall": empty, "weekly": empty}

    now = _utc_naive()
    weekly_from = now - timedelta(days=7)

    overall_rows = db.execute(
        select(
            Attempt.user_id,
            func.count(Attempt.id).label("attempts_finished"),
            func.avg(Attempt.percent).label("avg_percent"),
        ).where(Attempt.finished_at.is_not(None), Attempt.max_score > 0).group_by(Attempt.user_id)
    ).all()
    weekly_rows = db.execute(
        select(
            Attempt.user_id,
            func.count(Attempt.id).label("attempts_finished"),
            func.avg(Attempt.percent).label("avg_percent"),
        )
        .where(Attempt.finished_at.is_not(None), Attempt.max_score > 0, Attempt.finished_at >= weekly_from)
        .group_by(Attempt.user_id)
    ).all()

    def build_summary(rows):
        metrics = {
            student.id: {
                "user_id": student.id,
                "name": student.name,
                "grade": student.grade,
                "attempts_finished": 0,
                "average_percent": 0,
                "rating": 0.0,
            }
            for student in students
        }

        for row in rows:
            user_id = int(row.user_id)
            if user_id not in metrics:
                continue
            attempts_finished = int(row.attempts_finished or 0)
            avg_percent = int(round(float(row.avg_percent or 0)))
            activity_bonus = min(attempts_finished * 2, 20)
            quality_bonus = 10 if avg_percent >= 85 else 7 if avg_percent >= 70 else 4 if avg_percent >= 60 else 0
            rating = round(avg_percent + activity_bonus + quality_bonus, 1)
            metrics[user_id]["attempts_finished"] = attempts_finished
            metrics[user_id]["average_percent"] = avg_percent
            metrics[user_id]["rating"] = rating

        sorted_rows = sorted(
            metrics.values(),
            key=lambda item: (
                -float(item["rating"]),
                -int(item["average_percent"]),
                -int(item["attempts_finished"]),
                str(item["name"]).lower(),
                int(item["user_id"]),
            ),
        )

        for idx, item in enumerate(sorted_rows, start=1):
            item["rank"] = idx

        current = next((item for item in sorted_rows if int(item["user_id"]) == current_user_id), None)
        current_rank = int(current["rank"]) if current else total_students
        current_rating = float(current["rating"]) if current else 0.0
        top = list(sorted_rows[:top_limit])
        if current and all(int(item["user_id"]) != current_user_id for item in top):
            top.append(current)

        return {
            "total_students": total_students,
            "current_user_rank": current_rank,
            "current_user_rating": current_rating,
            "top": top,
        }

    return {
        "overall": build_summary(overall_rows),
        "weekly": build_summary(weekly_rows),
    }


def get_week_activity_for_user(
    db: Session,
    user_id: int,
    grade: int | None = None,
) -> dict[str, list[dict[str, int | str]]]:
    now = _utc_naive()
    day_start = datetime(now.year, now.month, now.day)
    week_start = day_start - timedelta(days=6)

    days = []
    for offset in range(7):
        current = week_start + timedelta(days=offset)
        key = current.date().isoformat()
        days.append({
            "date": key,
            "attempts": 0,
            "tasks": 0,
            "total": 0,
        })
    day_map = {item["date"]: item for item in days}

    exam_type = _exam_type_for_grade(grade)

    attempts_stmt = (
        select(
            func.date(Attempt.finished_at).label("day"),
            func.count(func.distinct(Attempt.id)).label("cnt"),
        )
        .select_from(Attempt)
        .join(AttemptAnswer, AttemptAnswer.attempt_id == Attempt.id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(
            Attempt.user_id == user_id,
            Attempt.finished_at.is_not(None),
            Attempt.finished_at >= week_start,
            Attempt.max_score > 0,
        )
        .group_by(func.date(Attempt.finished_at))
    )
    if grade is not None:
        attempts_stmt = attempts_stmt.where(Task.grade == grade)
    if exam_type is not None:
        attempts_stmt = attempts_stmt.where(func.lower(Task.exam_type) == exam_type)
    attempts_rows = db.execute(attempts_stmt).all()

    tasks_stmt = (
        select(
            func.date(AttemptAnswer.checked_at).label("day"),
            func.count(func.distinct(AttemptAnswer.task_id)).label("cnt"),
        )
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(
            Attempt.user_id == user_id,
            AttemptAnswer.checked_at.is_not(None),
            AttemptAnswer.user_answer.is_not(None),
            AttemptAnswer.checked_at >= week_start,
        )
        .group_by(func.date(AttemptAnswer.checked_at))
    )
    if grade is not None:
        tasks_stmt = tasks_stmt.where(Task.grade == grade)
    if exam_type is not None:
        tasks_stmt = tasks_stmt.where(func.lower(Task.exam_type) == exam_type)
    tasks_rows = db.execute(tasks_stmt).all()

    for row in attempts_rows:
        key = str(row.day)
        item = day_map.get(key)
        if item:
            item["attempts"] = int(row.cnt or 0)

    for row in tasks_rows:
        key = str(row.day)
        item = day_map.get(key)
        if item:
            item["tasks"] = int(row.cnt or 0)

    for item in days:
        item["total"] = int(item["attempts"]) + int(item["tasks"])

    return {"days": days}


def get_recommended_topics_for_user(
    db: Session,
    *,
    user_id: int,
    grade: int | None,
    limit: int = 3,
) -> dict[str, list[dict[str, int | str | None]]]:
    categories_stmt = select(TaskCategory).order_by(TaskCategory.sort_order.asc(), TaskCategory.id.asc())
    recommendation_user = db.get(User, user_id)
    if not (recommendation_user and has_feature(recommendation_user, "theory_full")):
        categories_stmt = categories_stmt.where(TaskCategory.sort_order <= 3)
    exam_type = _exam_type_for_grade(grade)
    if grade is not None:
        categories_stmt = categories_stmt.where(TaskCategory.grade == grade)
    if exam_type is not None:
        categories_stmt = categories_stmt.where(func.lower(TaskCategory.exam_type) == exam_type)
    categories = list(db.execute(categories_stmt).scalars().all())
    if not categories:
        return {"items": []}

    category_ids = [int(c.id) for c in categories]
    metrics = {
        int(c.id): {
            "category_id": int(c.id),
            "theory_slug": None,
            "title": c.title,
            "exam_type": c.exam_type,
            "attempted": 0,
            "correct": 0,
            "theory_done": False,
        }
        for c in categories
    }

    answers_rows = db.execute(
        select(
            Task.category_id.label("category_id"),
            func.count(AttemptAnswer.id).label("attempted"),
            func.sum(case((AttemptAnswer.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(
            Attempt.user_id == user_id,
            Task.category_id.is_not(None),
            Task.category_id.in_(category_ids),
        )
        .group_by(Task.category_id)
    ).all()

    theory_rows = db.execute(
        select(TheoryTopic.category_id)
        .join(TheoryTopicProgress, TheoryTopicProgress.topic_id == TheoryTopic.id)
        .where(
            TheoryTopicProgress.user_id == user_id,
            TheoryTopic.category_id.is_not(None),
            TheoryTopic.category_id.in_(category_ids),
        )
        .group_by(TheoryTopic.category_id)
    ).all()

    theory_slug_rows = db.execute(
        select(TheoryTopic.category_id, TheoryTopic.slug).where(
            TheoryTopic.category_id.is_not(None),
            TheoryTopic.category_id.in_(category_ids),
        )
    ).all()

    for row in answers_rows:
        cid = int(row.category_id)
        item = metrics.get(cid)
        if not item:
            continue
        item["attempted"] = int(row.attempted or 0)
        item["correct"] = int(row.correct or 0)

    for row in theory_rows:
        cid = int(row.category_id)
        item = metrics.get(cid)
        if item:
            item["theory_done"] = True

    for row in theory_slug_rows:
        cid = int(row.category_id)
        item = metrics.get(cid)
        if item and not item.get("theory_slug"):
            item["theory_slug"] = str(row.slug or "")

    scored = []
    for item in metrics.values():
        attempted = int(item["attempted"])
        correct = int(item["correct"])
        theory_done = bool(item["theory_done"])
        accuracy = round((correct / attempted) * 100) if attempted > 0 else 0
        practice_component = min(attempted * 10, 40)
        theory_component = 25 if theory_done else 0
        progress_percent = max(0, min(100, int(round((accuracy * 0.35) + practice_component + theory_component))))
        priority_score = progress_percent + (15 if attempted == 0 else 0)
        scored.append(
            {
                "category_id": item["category_id"],
                "theory_slug": item["theory_slug"],
                "title": item["title"],
                "progress_percent": progress_percent,
                "exam_type": item["exam_type"],
                "_priority": priority_score,
            }
        )

    scored.sort(key=lambda x: (int(x["_priority"]), int(x["progress_percent"]), str(x["title"]).lower()))
    result = [{k: v for k, v in row.items() if not k.startswith("_")} for row in scored[: max(1, int(limit))]]
    return {"items": result}
