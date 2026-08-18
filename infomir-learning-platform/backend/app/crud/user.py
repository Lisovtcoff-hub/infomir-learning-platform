import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from decimal import Decimal

from backend.app.core.security import hash_password, verify_and_update_password, verify_password
from backend.app.models.tariff import Tariff
from backend.app.models.teacher import TeacherProfile
from backend.app.models.user import User, UserProfile
from backend.app.schemas.user import UserCreate, UserProfileUpdate


def ensure_teacher_profile(db: Session, user_id: int) -> TeacherProfile:
    profile = db.get(TeacherProfile, user_id)
    if profile:
        return profile
    for _ in range(10):
        code = f"T-{secrets.token_hex(6).upper()}"
        exists = db.execute(select(TeacherProfile.user_id).where(TeacherProfile.invite_code == code)).first()
        if not exists:
            profile = TeacherProfile(
                user_id=user_id,
                invite_code=code,
                commission_percent=Decimal("20.00"),
            )
            db.add(profile)
            db.flush()
            return profile
    raise RuntimeError("Could not allocate a unique teacher code")


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.strip().lower())
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, payload: UserCreate, *, role: str = "student", auto_commit: bool = True) -> User:
    free_tariff = db.execute(select(Tariff).where(Tariff.code == "free")).scalar_one_or_none()
    if not free_tariff:
        free_tariff = Tariff(
            code="free",
            title="Бесплатный",
            price=0,
            duration_days=36500,
            description="Базовый доступ",
            features_json='["theory_basic", "practice_basic"]',
            is_active=True,
        )
        db.add(free_tariff)
        db.flush()
    user = User(
        name=payload.name,
        email=str(payload.email).strip().lower(),
        password_hash=hash_password(payload.password),
        grade=payload.grade,
        paid_tariff_id=free_tariff.id if free_tariff else None,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    profile = UserProfile(user_id=user.id)
    db.add(profile)
    if auto_commit:
        db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    verified, replacement_hash = verify_and_update_password(password, user.password_hash)
    if not verified:
        return None
    if replacement_hash:
        user.password_hash = replacement_hash
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def update_user_profile(db: Session, user_id: int, payload: UserProfileUpdate) -> UserProfile | None:
    profile = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if not profile:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_user_main(db: Session, user: User, *, name: str, grade: int | None) -> User:
    user.name = name
    user.grade = grade
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_user_password(db: Session, user: User, *, old_password: str, new_password: str) -> bool:
    if not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    user.session_version = int(user.session_version or 0) + 1
    db.add(user)
    db.commit()
    return True


def get_user_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
