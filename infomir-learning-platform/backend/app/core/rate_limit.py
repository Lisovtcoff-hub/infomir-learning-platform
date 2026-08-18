from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from backend.app.core.config import settings


class InMemoryRateLimiter:
    """Small single-process limiter. Use Redis at the reverse proxy for multi-worker production."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._last_seen: dict[str, float] = {}
        self._lock = Lock()
        self._checks = 0

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._checks += 1
            if self._checks % 1000 == 0:
                stale_before = now - 3600
                for stale_key in [item for item, seen in self._last_seen.items() if seen < stale_before]:
                    self._events.pop(stale_key, None)
                    self._last_seen.pop(stale_key, None)
            bucket = self._events[key]
            self._last_seen[key] = now
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Try again later.",
                    headers={"Retry-After": str(window_seconds)},
                )
            bucket.append(now)


rate_limiter = InMemoryRateLimiter()


def client_key(request: Request, scope: str, identity: str = "") -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() if settings.trust_proxy_headers else ""
    host = forwarded or (request.client.host if request.client else "unknown")
    return f"{scope}:{host}:{identity.strip().lower()}"
