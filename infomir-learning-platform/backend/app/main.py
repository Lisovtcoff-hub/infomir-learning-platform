
from pathlib import Path
import logging
from time import monotonic
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.admin_app import create_admin_app
from backend.app.api.routes import attempts, auth, payments, tariffs, tasks, teacher, theory, users, variants
from backend.app.core.config import settings
import backend.app.db.model_registry  # noqa: F401
from backend.app.db.session import get_db

public_app = FastAPI(title=settings.project_name, debug=settings.debug)
admin_app = create_admin_app()

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

public_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger("infomir.http")


@public_app.middleware("http")
async def add_security_headers(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.max_request_body_bytes:
        return PlainTextResponse("Request body too large", status_code=413)
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 64 or not all(ch.isalnum() or ch in "-_" for ch in request_id):
        request_id = uuid4().hex
    started = monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
        raise
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        round((monotonic() - started) * 1000, 2),
        request_id,
    )
    return response


@public_app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@public_app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/templates/public/index.html")


@public_app.get("/admin", include_in_schema=False)
def admin_redirect(request: Request):
    admin_host = settings.admin_hosts[0] if settings.admin_hosts else "admin.localhost"
    port = request.url.port
    authority = f"{admin_host}:{port}" if port and port not in {80, 443} else admin_host
    return RedirectResponse(url=f"{request.url.scheme}://{authority}/dashboard")


public_app.include_router(auth.router, prefix="/api")
public_app.include_router(payments.router, prefix="/api")
public_app.include_router(users.router, prefix="/api")
public_app.include_router(theory.router, prefix="/api")
public_app.include_router(tasks.router, prefix="/api")
public_app.include_router(variants.router, prefix="/api")
public_app.include_router(attempts.router, prefix="/api")
public_app.include_router(tariffs.router, prefix="/api")
public_app.include_router(teacher.router, prefix="/api")

public_app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
public_app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR, html=True), name="templates")


class HostBasedDispatcher:
    def __init__(self, public_asgi, admin_asgi):
        self.public_asgi = public_asgi
        self.admin_asgi = admin_asgi

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in {"http", "websocket"}:
            await self.public_asgi(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host = headers.get("host", "").split(":")[0].lower()

        if host in set(settings.admin_hosts):
            await self.admin_asgi(scope, receive, send)
            return

        if host not in set(settings.allowed_hosts):
            response = PlainTextResponse("Invalid host header", status_code=400)
            await response(scope, receive, send)
            return

        await self.public_asgi(scope, receive, send)


app = HostBasedDispatcher(public_app, admin_app)
