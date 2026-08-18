from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import require_roles
from backend.app.crud.attempt import get_recommended_topics_for_user
from backend.app.db.session import get_db
from backend.app.models.attempt import Attempt
from backend.app.models.attempt import AttemptAnswer
from backend.app.models.task import Task, TaskCategory
from backend.app.models.tariff import Payment, Tariff, TeacherCommission
from backend.app.models.teacher import TeacherGroup, TeacherGroupMember, TeacherProfile, TeacherWithdrawal
from backend.app.models.user import User
from backend.app.crud.user import ensure_teacher_profile
from backend.app.models.variant import Variant
from backend.app.schemas.teacher import (
    TeacherDashboardStatsRead,
    TeacherEarningsHistoryRead,
    TeacherEarningHistoryItemRead,
    TeacherGroupWithStudentsRead,
    TeacherGroupedStudentRead,
    TeacherGroupCreate,
    TeacherGroupUpdate,
    TeacherGroupRead,
    TeacherStudentDetailsRead,
    TeacherStudentDisconnectRead,
    TeacherStudentGroupRead,
    TeacherStudentMoveRead,
    TeacherStudentMoveRequest,
    TeacherStudentRead,
    TeacherStudentTaskHistoryRead,
    TeacherStudentVariantResultRead,
    TeacherWithdrawalCreateRead,
    TeacherWithdrawalHistoryItemRead,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])


def _teacher_total_earned(db: Session, teacher_id: int) -> float:
    total_raw = db.execute(
        select(func.sum(TeacherCommission.amount)).where(
            TeacherCommission.teacher_id == teacher_id,
            TeacherCommission.status == "available",
        )
    ).scalar_one_or_none()
    return round(float(total_raw or 0), 2)


def _teacher_total_withdrawn(db: Session, teacher_id: int) -> float:
    withdrawn_raw = db.execute(
        select(func.sum(TeacherWithdrawal.amount)).where(
            TeacherWithdrawal.teacher_id == teacher_id,
            TeacherWithdrawal.status.in_(["requested", "processing", "paid"]),
        )
    ).scalar_one_or_none()
    return round(float(withdrawn_raw or 0), 2)


def _normalize_topic_title(value: str | None) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text


def _exam_type_for_grade(grade: int | None) -> str | None:
    if grade in (7, 8):
        return "vpr"
    if grade == 9:
        return "oge"
    return None


def _format_public_task_code(
    *,
    task_id: int,
    task_exam_type: str | None,
    category_exam_type: str | None,
    task_grade: int | None,
    category_grade: int | None,
    student_grade: int | None,
) -> str:
    exam_raw = str(task_exam_type or category_exam_type or "").strip().lower()
    grade = task_grade or category_grade or student_grade

    if exam_raw == "vpr":
        grade_part = int(grade) if grade is not None else 7
        return f"VPR{grade_part}-{int(task_id):03d}"
    if exam_raw == "oge":
        return f"OGE-{int(task_id):03d}"

    if grade in (7, 8):
        return f"VPR{int(grade)}-{int(task_id):03d}"
    if grade == 9:
        return f"OGE-{int(task_id):03d}"
    return f"TASK-{int(task_id):03d}"


@router.get("/me")
def teacher_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    profile = ensure_teacher_profile(db, current_user.id)
    db.commit()
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "invite_code": profile.invite_code,
        "commission_percent": float(profile.commission_percent),
    }


@router.get("/students", response_model=list[TeacherStudentRead])
def list_teacher_students(
    grade: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    user_role = (current_user.role or "").strip().lower()
    if user_role == "admin":
        stmt = select(User).where(User.role == "student")
        if grade is not None:
            stmt = stmt.where(User.grade == grade)
        stmt = stmt.order_by(User.name.asc(), User.id.asc())
        return db.execute(stmt).scalars().all()

    stmt = (
        select(User)
        .join(TeacherGroupMember, TeacherGroupMember.student_id == User.id)
        .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
        .where(TeacherGroup.teacher_id == current_user.id, User.role == "student")
        .distinct()
    )
    if grade is not None:
        stmt = stmt.where(User.grade == grade)
    stmt = stmt.order_by(User.name.asc(), User.id.asc())
    return db.execute(stmt).scalars().all()


@router.get("/dashboard-stats", response_model=TeacherDashboardStatsRead)
def get_teacher_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    student_ids_subquery = (
        select(TeacherGroupMember.student_id)
        .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
        .where(TeacherGroup.teacher_id == current_user.id)
        .distinct()
        .subquery()
    )

    connected_students_count = int(
        db.execute(select(func.count()).select_from(student_ids_subquery)).scalar_one() or 0
    )

    average_percent_raw = db.execute(
        select(func.avg(Attempt.percent))
        .where(Attempt.user_id.in_(select(student_ids_subquery.c.student_id)))
        .where(Attempt.finished_at.is_not(None))
    ).scalar_one_or_none()
    average_percent = int(round(float(average_percent_raw or 0)))

    average_grade_raw = db.execute(
        select(func.avg(Attempt.grade_mark))
        .where(Attempt.user_id.in_(select(student_ids_subquery.c.student_id)))
        .where(Attempt.finished_at.is_not(None))
        .where(Attempt.grade_mark.is_not(None))
    ).scalar_one_or_none()
    average_grade = round(float(average_grade_raw or 0), 1)

    earnings_total = _teacher_total_earned(db, current_user.id)
    total_withdrawn = _teacher_total_withdrawn(db, current_user.id)
    current_balance = max(0.0, round(float(earnings_total) - float(total_withdrawn), 2))

    return TeacherDashboardStatsRead(
        connected_students_count=connected_students_count,
        average_percent=average_percent,
        average_grade=average_grade,
        earnings_total=earnings_total,
        current_balance=current_balance,
    )


@router.get("/earnings-history", response_model=TeacherEarningsHistoryRead)
def get_teacher_earnings_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group_title_subquery = (
        select(TeacherGroup.title)
        .join(TeacherGroupMember, TeacherGroupMember.group_id == TeacherGroup.id)
        .where(
            TeacherGroup.teacher_id == current_user.id,
            TeacherGroupMember.student_id == TeacherCommission.student_id,
        )
        .order_by(TeacherGroup.id.asc())
        .limit(1)
        .scalar_subquery()
    )

    rows = db.execute(
        select(
            Payment.id.label("payment_id"),
            User.id.label("student_id"),
            User.name.label("student_name"),
            User.email.label("student_email"),
            Tariff.title.label("tariff_title"),
            Payment.amount.label("tariff_price"),
            Payment.paid_at.label("paid_at"),
            TeacherCommission.amount.label("teacher_share"),
            group_title_subquery.label("group_title"),
        )
        .select_from(TeacherCommission)
        .join(Payment, Payment.id == TeacherCommission.payment_id)
        .join(User, User.id == TeacherCommission.student_id)
        .join(Tariff, Tariff.id == Payment.tariff_id)
        .where(
            TeacherCommission.teacher_id == current_user.id,
            TeacherCommission.status == "available",
        )
        .order_by(TeacherCommission.created_at.desc(), TeacherCommission.id.desc())
    ).all()

    items: list[TeacherEarningHistoryItemRead] = []
    total = 0.0
    for row in rows:
        tariff_price = float(row.tariff_price or 0)
        teacher_share = round(float(row.teacher_share or 0), 2)
        total += teacher_share
        paid_at = row.paid_at.isoformat(sep=" ", timespec="seconds") if row.paid_at else ""
        items.append(
            TeacherEarningHistoryItemRead(
                payment_id=int(row.payment_id),
                student_id=int(row.student_id),
                student_name=str(row.student_name or ""),
                student_email=str(row.student_email or ""),
                group_title=str(row.group_title) if row.group_title else None,
                tariff_title=str(row.tariff_title or ""),
                tariff_price=tariff_price,
                teacher_share=teacher_share,
                paid_at=paid_at,
            )
        )

    withdrawals_rows = db.execute(
        select(TeacherWithdrawal)
        .where(TeacherWithdrawal.teacher_id == current_user.id)
        .order_by(TeacherWithdrawal.created_at.desc(), TeacherWithdrawal.id.desc())
    ).scalars().all()
    withdrawals = [
        TeacherWithdrawalHistoryItemRead(
            id=int(row.id),
            amount=round(float(row.amount or 0), 2),
            status=str(row.status or "requested"),
            created_at=row.created_at.isoformat(sep=" ", timespec="seconds") if row.created_at else "",
        )
        for row in withdrawals_rows
    ]
    total_withdrawn = _teacher_total_withdrawn(db, current_user.id)
    current_balance = max(0.0, round(float(total) - float(total_withdrawn), 2))
    return TeacherEarningsHistoryRead(
        total_earned=round(total, 2),
        current_balance=current_balance,
        withdrawals=withdrawals,
        items=items,
    )


@router.get("/groups", response_model=list[TeacherGroupRead])
def list_teacher_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    stmt = (
        select(
            TeacherGroup.id,
            TeacherGroup.title,
            func.count(TeacherGroupMember.id).label("students_count"),
        )
        .outerjoin(TeacherGroupMember, TeacherGroupMember.group_id == TeacherGroup.id)
        .where(TeacherGroup.teacher_id == current_user.id)
        .group_by(TeacherGroup.id, TeacherGroup.title)
        .order_by(TeacherGroup.title.asc())
    )
    rows = db.execute(stmt).all()
    return [TeacherGroupRead(id=row.id, title=row.title, students_count=row.students_count) for row in rows]


@router.post("/withdrawals", response_model=TeacherWithdrawalCreateRead, status_code=201)
def create_teacher_withdrawal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    db.execute(select(User.id).where(User.id == current_user.id).with_for_update()).scalar_one()
    active = db.execute(
        select(TeacherWithdrawal.id).where(
            TeacherWithdrawal.teacher_id == current_user.id,
            TeacherWithdrawal.status.in_(["requested", "processing"]),
        )
    ).scalar_one_or_none()
    if active is not None:
        raise HTTPException(status_code=409, detail="An active withdrawal request already exists")

    total_earned = Decimal(str(_teacher_total_earned(db, current_user.id)))
    total_withdrawn = Decimal(str(_teacher_total_withdrawn(db, current_user.id)))
    current_balance = max(Decimal("0.00"), (total_earned - total_withdrawn).quantize(Decimal("0.01")))
    if current_balance <= 0:
        raise HTTPException(status_code=400, detail="Current balance is zero")

    withdrawal = TeacherWithdrawal(teacher_id=current_user.id, amount=current_balance)
    db.add(withdrawal)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active withdrawal request already exists") from exc
    db.refresh(withdrawal)

    return TeacherWithdrawalCreateRead(
        id=int(withdrawal.id),
        amount=float(withdrawal.amount or 0),
        created_at=withdrawal.created_at.isoformat(sep=" ", timespec="seconds") if withdrawal.created_at else "",
        current_balance=0.0,
        status=str(withdrawal.status),
    )


@router.get("/groups-with-students", response_model=list[TeacherGroupWithStudentsRead])
def list_teacher_groups_with_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    groups_stmt = (
        select(
            TeacherGroup.id,
            TeacherGroup.title,
            func.count(TeacherGroupMember.id).label("students_count"),
        )
        .outerjoin(TeacherGroupMember, TeacherGroupMember.group_id == TeacherGroup.id)
        .where(TeacherGroup.teacher_id == current_user.id)
        .group_by(TeacherGroup.id, TeacherGroup.title)
        .order_by(TeacherGroup.title.asc())
    )
    groups_rows = db.execute(groups_stmt).all()
    if not groups_rows:
        return []

    group_ids = [int(row.id) for row in groups_rows]
    students_stmt = (
        select(
            TeacherGroupMember.group_id,
            User.id,
            User.name,
            User.grade,
            Tariff.title.label("tariff_title"),
        )
        .join(User, User.id == TeacherGroupMember.student_id)
        .outerjoin(Tariff, Tariff.id == User.paid_tariff_id)
        .where(TeacherGroupMember.group_id.in_(group_ids))
        .group_by(TeacherGroupMember.group_id, User.id, User.name, User.grade, Tariff.title)
        .order_by(TeacherGroupMember.group_id.asc(), User.name.asc(), User.id.asc())
    )
    student_rows = db.execute(students_stmt).all()

    student_ids = sorted({int(row.id) for row in student_rows})
    predicted_by_student: dict[int, float] = {}
    if student_ids:
        attempts_stmt = (
            select(
                Attempt.user_id,
                Attempt.grade_mark,
                Variant.exam_type.label("exam_type"),
                Variant.grade.label("grade"),
            )
            .outerjoin(Variant, Variant.id == Attempt.variant_id)
            .where(Attempt.user_id.in_(student_ids))
            .where(Attempt.finished_at.is_not(None))
            .where(Attempt.max_score > 0)
            .where(Attempt.grade_mark.is_not(None))
            .where(func.lower(Attempt.mode).like("%variant%"))
            .order_by(Attempt.user_id.asc(), Attempt.id.desc())
        )
        attempt_rows = db.execute(attempts_stmt).all()
        grade_by_student: dict[int, int | None] = {int(row.id): row.grade for row in student_rows}
        grades_by_student: dict[int, list[int]] = {sid: [] for sid in student_ids}
        for row in attempt_rows:
            sid = int(row.user_id)
            student_grade = grade_by_student.get(sid)
            expected_exam = _exam_type_for_grade(student_grade)
            # Keep only variants matching the student's class profile.
            if expected_exam is not None:
                # If variant is linked, prefer its exam/grade validation.
                # For legacy attempts without variant row, we keep the record.
                row_exam = getattr(row, "exam_type", None)
                row_grade = getattr(row, "grade", None)
                if row_exam is not None and str(row_exam).strip().lower() != expected_exam:
                    continue
                if row_grade is not None and student_grade is not None and int(row_grade) != int(student_grade):
                    continue
            items = grades_by_student.setdefault(sid, [])
            if len(items) >= 5:
                continue
            items.append(int(row.grade_mark))

        for sid, grades in grades_by_student.items():
            if grades:
                predicted_by_student[sid] = round(sum(grades) / len(grades), 1)
            else:
                predicted_by_student[sid] = 0.0

    by_group: dict[int, list[TeacherGroupedStudentRead]] = {gid: [] for gid in group_ids}
    for row in student_rows:
        student_id = int(row.id)
        by_group[int(row.group_id)].append(
            TeacherGroupedStudentRead(
                id=student_id,
                name=str(row.name),
                grade=row.grade,
                predicted_grade=float(predicted_by_student.get(student_id, 0.0)),
                tariff_title=row.tariff_title,
            )
        )

    return [
        TeacherGroupWithStudentsRead(
            id=int(group.id),
            title=str(group.title),
            students_count=int(group.students_count or 0),
            students=by_group.get(int(group.id), []),
        )
        for group in groups_rows
    ]


@router.get("/students/{student_id}/details", response_model=TeacherStudentDetailsRead)
def get_teacher_student_details(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Student not found")

    linked = db.execute(
        select(func.count(TeacherGroupMember.id))
        .select_from(TeacherGroupMember)
        .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
        .where(TeacherGroup.teacher_id == current_user.id, TeacherGroupMember.student_id == student_id)
    ).scalar_one()
    if int(linked or 0) <= 0:
        raise HTTPException(status_code=403, detail="Student is not connected to your groups")
    expected_exam = _exam_type_for_grade(student.grade)

    solved_stmt = (
        select(func.count(func.distinct(AttemptAnswer.task_id)))
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(Attempt.user_id == student_id, AttemptAnswer.user_answer.is_not(None))
    )
    correct_stmt = (
        select(func.count(AttemptAnswer.id))
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(Attempt.user_id == student_id, AttemptAnswer.is_correct.is_(True))
    )
    wrong_stmt = (
        select(func.count(AttemptAnswer.id))
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .where(Attempt.user_id == student_id, AttemptAnswer.is_correct.is_(False))
    )
    if student.grade is not None:
        solved_stmt = solved_stmt.where(Task.grade == student.grade)
        correct_stmt = correct_stmt.where(Task.grade == student.grade)
        wrong_stmt = wrong_stmt.where(Task.grade == student.grade)
    if expected_exam is not None:
        solved_stmt = solved_stmt.where(func.lower(Task.exam_type) == expected_exam)
        correct_stmt = correct_stmt.where(func.lower(Task.exam_type) == expected_exam)
        wrong_stmt = wrong_stmt.where(func.lower(Task.exam_type) == expected_exam)

    solved_total = int(db.execute(solved_stmt).scalar_one() or 0)
    correct_total = int(db.execute(correct_stmt).scalar_one() or 0)
    wrong_total = int(db.execute(wrong_stmt).scalar_one() or 0)

    # Fallback for users that have finished attempts but no persisted AttemptAnswer rows.
    if solved_total == 0 and correct_total == 0 and wrong_total == 0:
        agg = db.execute(
            select(
                func.sum(Attempt.max_score).label("sum_max_score"),
                func.sum(Attempt.score).label("sum_score"),
            )
            .where(Attempt.user_id == student_id, Attempt.finished_at.is_not(None), Attempt.max_score > 0)
        ).one()
        sum_max_score = int(agg.sum_max_score or 0)
        sum_score = int(agg.sum_score or 0)
        if sum_max_score > 0:
            solved_total = sum_max_score
            correct_total = max(0, min(sum_score, sum_max_score))
            wrong_total = max(0, sum_max_score - correct_total)

    variant_stmt = (
        select(
            Attempt.id,
            Attempt.variant_id,
            Attempt.mode,
            Attempt.percent,
            Attempt.grade_mark,
            Attempt.finished_at,
        )
        .outerjoin(Variant, Variant.id == Attempt.variant_id)
        .where(Attempt.user_id == student_id, Attempt.finished_at.is_not(None), Attempt.max_score > 0)
        .where(
            func.lower(Attempt.mode).like("%variant%")
            | func.lower(Attempt.mode).like("%practice_seed%")
        )
    )
    if student.grade is not None:
        variant_stmt = variant_stmt.where(Variant.id.is_(None) | (Variant.grade == student.grade))
    if expected_exam is not None:
        variant_stmt = variant_stmt.where(Variant.id.is_(None) | (func.lower(Variant.exam_type) == expected_exam))
    variant_rows = db.execute(
        variant_stmt.order_by(Attempt.finished_at.desc(), Attempt.id.desc()).limit(20)
    ).all()
    variant_results = [
        TeacherStudentVariantResultRead(
            attempt_id=int(row.id),
            title=(
                f"Вариант №{int(row.variant_id)}"
                if row.variant_id is not None
                else ("Тренировка" if "practice" in str(row.mode or "").lower() else "Вариант")
            ),
            percent=int(row.percent or 0),
            grade_mark=int(row.grade_mark) if row.grade_mark is not None else None,
            finished_at=row.finished_at.isoformat(sep=" ", timespec="seconds") if row.finished_at else None,
        )
        for row in variant_rows
    ]

    group_rows = db.execute(
        select(TeacherGroup.id, TeacherGroup.title)
        .join(TeacherGroupMember, TeacherGroupMember.group_id == TeacherGroup.id)
        .where(TeacherGroup.teacher_id == current_user.id, TeacherGroupMember.student_id == student_id)
        .order_by(TeacherGroup.title.asc(), TeacherGroup.id.asc())
    ).all()
    current_groups = [TeacherStudentGroupRead(id=int(row.id), title=str(row.title)) for row in group_rows]

    task_stmt = (
        select(
            Attempt.id.label("attempt_id"),
            AttemptAnswer.task_id,
            Task.category_id.label("topic_id"),
            Task.exam_type.label("task_exam_type"),
            Task.grade.label("task_grade"),
            TaskCategory.exam_type.label("category_exam_type"),
            TaskCategory.grade.label("category_grade"),
            TaskCategory.title.label("topic_title"),
            Task.title.label("task_title"),
            AttemptAnswer.is_correct,
            AttemptAnswer.checked_at,
            AttemptAnswer.user_answer,
            Task.answer.label("correct_answer"),
            Task.question.label("task_prompt"),
        )
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Task, Task.id == AttemptAnswer.task_id)
        .outerjoin(TaskCategory, TaskCategory.id == Task.category_id)
        .where(Attempt.user_id == student_id, AttemptAnswer.user_answer.is_not(None))
    )
    if student.grade is not None:
        task_stmt = task_stmt.where(Task.grade == student.grade)
    if expected_exam is not None:
        task_stmt = task_stmt.where(func.lower(Task.exam_type) == expected_exam)
    task_rows = db.execute(
        task_stmt.order_by(AttemptAnswer.checked_at.desc(), AttemptAnswer.id.desc()).limit(100)
    ).all()
    task_history = [
        TeacherStudentTaskHistoryRead(
            attempt_id=int(row.attempt_id),
            task_id=int(row.task_id),
            topic_id=int(row.topic_id) if row.topic_id is not None else None,
            task_code=_format_public_task_code(
                task_id=int(row.task_id),
                task_exam_type=row.task_exam_type,
                category_exam_type=row.category_exam_type,
                task_grade=row.task_grade,
                category_grade=row.category_grade,
                student_grade=student.grade,
            ),
            topic_title=_normalize_topic_title(row.topic_title) or "Без темы",
            is_correct=bool(row.is_correct) if row.is_correct is not None else None,
            checked_at=row.checked_at.isoformat(sep=" ", timespec="seconds") if row.checked_at else None,
            user_answer=str(row.user_answer) if row.user_answer is not None else None,
            correct_answer=str(row.correct_answer) if row.correct_answer is not None else None,
            task_prompt=str(row.task_prompt) if row.task_prompt is not None else None,
        )
        for row in task_rows
    ]


    weak_topics_payload = get_recommended_topics_for_user(
        db,
        user_id=student_id,
        grade=student.grade,
        limit=5,
    )
    weak_topics = [_normalize_topic_title(item.get("title")) for item in weak_topics_payload.get("items", [])]
    weak_topics = [item for item in weak_topics if item]

    return TeacherStudentDetailsRead(
        id=int(student.id),
        name=str(student.name or ""),
        email=str(student.email or ""),
        grade=student.grade,
        tariff_title=student.paid_tariff_title,
        solved_total=solved_total,
        correct_total=correct_total,
        wrong_total=wrong_total,
        current_groups=current_groups,
        task_history=task_history,
        variant_results=variant_results,
        weak_topics=weak_topics,
    )


@router.delete("/students/{student_id}", response_model=TeacherStudentDisconnectRead)
def disconnect_student_from_teacher(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    members = list(
        db.execute(
            select(TeacherGroupMember)
            .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
            .where(TeacherGroup.teacher_id == current_user.id, TeacherGroupMember.student_id == student_id)
        ).scalars().all()
    )
    if not members:
        raise HTTPException(status_code=404, detail="Student is not connected to your groups")

    removed = 0
    for member in members:
        db.delete(member)
        removed += 1
    db.commit()

    return TeacherStudentDisconnectRead(student_id=student_id, removed_from_groups=removed)


@router.post("/students/{student_id}/move", response_model=TeacherStudentMoveRead)
def move_student_between_teacher_groups(
    student_id: int,
    payload: TeacherStudentMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    source_group = db.get(TeacherGroup, payload.source_group_id)
    target_group = db.get(TeacherGroup, payload.target_group_id)
    if not source_group or source_group.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source group not found")
    if not target_group or target_group.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Target group not found")
    if source_group.id == target_group.id:
        raise HTTPException(status_code=400, detail="Source and target groups must be different")

    source_member = db.execute(
        select(TeacherGroupMember).where(
            TeacherGroupMember.group_id == source_group.id,
            TeacherGroupMember.student_id == student_id,
        )
    ).scalar_one_or_none()
    if not source_member:
        raise HTTPException(status_code=404, detail="Student is not in source group")

    target_member = db.execute(
        select(TeacherGroupMember).where(
            TeacherGroupMember.group_id == target_group.id,
            TeacherGroupMember.student_id == student_id,
        )
    ).scalar_one_or_none()
    db.delete(source_member)
    db.flush()
    if not target_member:
        db.add(TeacherGroupMember(group_id=target_group.id, student_id=student_id))
    db.commit()

    return TeacherStudentMoveRead(
        student_id=student_id,
        source_group_id=source_group.id,
        target_group_id=target_group.id,
    )


@router.post("/groups", response_model=TeacherGroupRead, status_code=201)
def create_teacher_group(
    payload: TeacherGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    group = TeacherGroup(teacher_id=current_user.id, title=title)
    db.add(group)
    db.commit()
    db.refresh(group)
    return TeacherGroupRead(id=group.id, title=group.title, students_count=0)


@router.patch("/groups/{group_id}", response_model=TeacherGroupRead)
def update_teacher_group(
    group_id: int,
    payload: TeacherGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = db.get(TeacherGroup, group_id)
    if not group or group.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Group not found")

    title = str(payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Group title is required")

    group.title = title
    db.add(group)
    db.commit()
    db.refresh(group)

    students_count = int(
        db.execute(
            select(func.count(TeacherGroupMember.id)).where(TeacherGroupMember.group_id == group_id)
        ).scalar_one()
        or 0
    )
    return TeacherGroupRead(id=group.id, title=group.title, students_count=students_count)


@router.delete("/groups/{group_id}", response_model=TeacherGroupRead)
def delete_teacher_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = db.get(TeacherGroup, group_id)
    if not group or group.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Group not found")

    students_count = int(
        db.execute(
            select(func.count(TeacherGroupMember.id)).where(TeacherGroupMember.group_id == group_id)
        ).scalar_one()
        or 0
    )
    if students_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete non-empty group")

    response = TeacherGroupRead(id=group.id, title=group.title, students_count=0)
    db.delete(group)
    db.commit()
    return response


@router.delete("/groups/{group_id}/students/{student_id}", response_model=TeacherGroupRead)
def remove_student_from_group(
    group_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = db.get(TeacherGroup, group_id)
    if not group or group.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Group not found")

    member_stmt = select(TeacherGroupMember).where(
        TeacherGroupMember.group_id == group_id,
        TeacherGroupMember.student_id == student_id,
    )
    member = db.execute(member_stmt).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Student is not in group")

    db.delete(member)
    db.commit()

    count_stmt = select(func.count(TeacherGroupMember.id)).where(TeacherGroupMember.group_id == group_id)
    students_count = int(db.execute(count_stmt).scalar_one() or 0)
    return TeacherGroupRead(id=group.id, title=group.title, students_count=students_count)

