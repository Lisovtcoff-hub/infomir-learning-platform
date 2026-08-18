from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.crud.user import get_user_by_id
from backend.app.db.session import get_db
from backend.app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _extract_bearer(raw_token: str | None) -> str | None:
    if not raw_token:
        return None
    token = raw_token.strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Cookie(default=None, alias="infomir_access_token"),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer(cookie_token) or _extract_bearer(bearer_token)

    if not token:
        auth_header = request.headers.get("authorization")
        token = _extract_bearer(auth_header)

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if int(payload.get("sv", -1)) != int(user.session_version or 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")
    return user


def get_optional_current_user(
    request: Request,
    cookie_token: str | None = Cookie(default=None, alias="infomir_access_token"),
    db: Session = Depends(get_db),
) -> User | None:
    token = _extract_bearer(cookie_token) or _extract_bearer(request.headers.get("authorization"))
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active or int(payload.get("sv", -1)) != int(user.session_version or 0):
        return None
    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    normalized_roles = {role.strip().lower() for role in allowed_roles if role and role.strip()}

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").strip().lower()
        if user_role not in normalized_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return role_dependency
