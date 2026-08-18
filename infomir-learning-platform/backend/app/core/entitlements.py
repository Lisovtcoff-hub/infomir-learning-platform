from __future__ import annotations

from datetime import datetime, timezone
import json

from backend.app.models.user import User


def tariff_features(user: User) -> set[str]:
    tariff = user.paid_tariff
    if not tariff or not tariff.is_active:
        return set()
    expires_at = user.paid_tariff_expires_at
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return set()
    raw = tariff.features_json
    if not raw:
        return set()
    if isinstance(raw, list):
        return {str(item) for item in raw}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return set()
    return {str(item) for item in parsed} if isinstance(parsed, list) else set()


def has_feature(user: User, feature: str) -> bool:
    role = str(user.role or "").strip().lower()
    if role in {"teacher", "admin"}:
        return True
    return feature in tariff_features(user)
