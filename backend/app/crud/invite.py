from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.invite import TeacherInvite


def normalize_invite_code(code: str) -> str:
    return code.strip()


def hash_invite_code(code: str) -> str:
    normalized = normalize_invite_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_teacher_invite_by_code(db: Session, code: str) -> TeacherInvite | None:
    code_hash = hash_invite_code(code)
    stmt = select(TeacherInvite).where(TeacherInvite.code_hash == code_hash)
    return db.execute(stmt).scalar_one_or_none()


def validate_teacher_invite(invite: TeacherInvite | None, now: datetime | None = None) -> tuple[bool, str | None]:
    if not invite:
        return False, "Неверный код приглашения учителя."
    if not invite.is_active:
        return False, "Код приглашения отключен."
    current = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if invite.expires_at and current > invite.expires_at:
        return False, "Срок действия кода приглашения истек."
    if invite.used_count >= invite.max_uses:
        return False, "Код приглашения уже использован."
    return True, None


def consume_teacher_invite(db: Session, invite: TeacherInvite) -> TeacherInvite:
    invite.used_count += 1
    db.add(invite)
    return invite


def generate_teacher_invite_code() -> str:
    return secrets.token_urlsafe(24)


def create_teacher_invite(
    db: Session,
    *,
    created_by_admin_id: int | None,
    max_uses: int = 1,
    expires_at: datetime | None = None,
) -> tuple[TeacherInvite, str]:
    raw_code = generate_teacher_invite_code()
    invite = TeacherInvite(
        code_hash=hash_invite_code(raw_code),
        max_uses=max_uses,
        used_count=0,
        expires_at=expires_at,
        is_active=True,
        created_by_admin_id=created_by_admin_id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite, raw_code
