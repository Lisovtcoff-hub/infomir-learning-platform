from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import Request

from backend.app.api.deps import get_current_user, get_optional_current_user
from backend.app.core.config import settings
from backend.app.core.rate_limit import client_key, rate_limiter
from backend.app.core.security import create_access_token
from backend.app.crud.invite import consume_teacher_invite, get_teacher_invite_by_code, validate_teacher_invite
from backend.app.crud.user import authenticate_user, create_user, ensure_teacher_profile, get_user_by_email
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import SessionCreated
from backend.app.schemas.user import UserCreate, UserLogin, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "infomir_access_token"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check(client_key(request, "register", str(payload.email)), limit=5, window_seconds=3600)
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    role = "student"
    invite_to_consume = None
    if payload.invite_code:
        invite = get_teacher_invite_by_code(db, payload.invite_code)
        ok, reason = validate_teacher_invite(invite)
        if not ok:
            raise HTTPException(status_code=400, detail=reason or "Invalid invite code")
        role = "teacher"
        invite_to_consume = invite

    try:
        user = create_user(db, payload, role=role, auto_commit=False)
        if role == "teacher":
            ensure_teacher_profile(db, user.id)
        if invite_to_consume:
            consume_teacher_invite(db, invite_to_consume)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered") from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=SessionCreated)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limiter.check(client_key(request, "login", str(payload.email)), limit=8, window_seconds=300)
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(str(user.id), session_version=int(user.session_version or 0))
    _set_auth_cookie(response, token)
    return SessionCreated()


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if current_user:
        current_user.session_version = int(current_user.session_version or 0) + 1
        db.add(current_user)
        db.commit()
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
