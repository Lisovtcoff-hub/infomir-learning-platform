from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.exc import IntegrityError
from fastapi import Request

from backend.app.api.deps import get_current_user
from backend.app.core.rate_limit import client_key, rate_limiter
from backend.app.crud.attempt import get_leaderboard_for_user
from backend.app.crud.user import change_user_password, get_user_profile, update_user_main, update_user_profile
from backend.app.db.session import get_db
from backend.app.models.teacher import TeacherGroup, TeacherGroupMember, TeacherProfile
from backend.app.models.user import User
from backend.app.schemas.user import (
    UserLeaderboardRead,
    UserMeUpdate,
    UserPasswordChange,
    UserProfileRead,
    UserProfileUpdate,
    UserRead,
    UserTariffUpdate,
    TeacherConnectRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _build_user_read(db: Session, user: User) -> dict:
    payload = UserRead.model_validate(user).model_dump()
    payload["connected_group_title"] = None
    payload["connected_teacher_name"] = None

    if (user.role or "").strip().lower() != "student":
        return payload

    teacher_user = aliased(User)
    row = db.execute(
        select(TeacherGroup.title, teacher_user.name)
        .select_from(TeacherGroupMember)
        .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
        .join(teacher_user, teacher_user.id == TeacherGroup.teacher_id)
        .where(TeacherGroupMember.student_id == user.id)
        .order_by(TeacherGroup.id.asc())
        .limit(1)
    ).first()

    if row:
        payload["connected_group_title"] = str(row[0] or "")
        payload["connected_teacher_name"] = str(row[1] or "")

    return payload


@router.get("/me", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _build_user_read(db, current_user)


@router.patch("/me", response_model=UserRead)
def patch_me(
    payload: UserMeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = update_user_main(db, current_user, name=payload.name, grade=payload.grade)
    return _build_user_read(db, updated)


@router.patch("/me/tariff", response_model=UserRead)
def patch_me_tariff(
    payload: UserTariffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=410,
        detail="Direct tariff changes are disabled. Create a payment through /api/payments.",
    )


@router.post("/me/teacher", response_model=UserRead)
def connect_me_to_teacher(
    payload: TeacherConnectRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (current_user.role or "").strip().lower() != "student":
        raise HTTPException(status_code=403, detail="Only students can connect to a teacher")
    code = payload.invite_code.strip().upper()
    rate_limiter.check(client_key(request, "teacher-connect", str(current_user.id)), limit=5, window_seconds=300)

    profile = db.execute(select(TeacherProfile).where(TeacherProfile.invite_code == code)).scalar_one_or_none()
    teacher = db.get(User, profile.user_id) if profile else None
    if not profile or not teacher or not teacher.is_active or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher code not found")

    existing = db.execute(
        select(TeacherGroupMember, TeacherGroup.teacher_id)
        .join(TeacherGroup, TeacherGroup.id == TeacherGroupMember.group_id)
        .where(TeacherGroupMember.student_id == current_user.id)
    ).first()
    if existing:
        if int(existing.teacher_id) == int(teacher.id):
            return _build_user_read(db, current_user)
        raise HTTPException(status_code=409, detail="Student is already connected to another teacher")

    group = db.execute(
        select(TeacherGroup)
        .where(TeacherGroup.teacher_id == teacher.id)
        .order_by(TeacherGroup.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if not group:
        group = TeacherGroup(teacher_id=teacher.id, title="Основная группа")
        db.add(group)
        db.flush()
    db.add(TeacherGroupMember(group_id=group.id, student_id=current_user.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Student connection changed concurrently; refresh and try again") from exc
    return _build_user_read(db, current_user)


@router.delete("/me/teacher", response_model=UserRead)
def disconnect_me_from_teacher(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = list(
        db.execute(
            select(TeacherGroupMember).where(TeacherGroupMember.student_id == current_user.id)
        ).scalars().all()
    )
    for membership in memberships:
        db.delete(membership)
    db.commit()
    return _build_user_read(db, current_user)


@router.patch("/me/password")
def patch_me_password(
    payload: UserPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = change_user_password(
        db,
        current_user,
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return {"ok": True}


@router.get("/me/profile", response_model=UserProfileRead)
def get_me_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/me/profile", response_model=UserProfileRead)
def patch_me_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = update_user_profile(db, current_user.id, payload)
    return profile


@router.get("/me/leaderboard", response_model=UserLeaderboardRead)
def get_me_leaderboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_leaderboard_for_user(db, current_user_id=current_user.id)
