
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.rate_limit import client_key, rate_limiter
from backend.app.core.security import hash_password, verify_and_update_password
from backend.app.db.session import get_db
from backend.app.models.task import Task, TaskCategory
from backend.app.models.audit import AdminAuditLog
from backend.app.models.attempt import AttemptAnswer
from backend.app.models.theory import TheoryTopic
from backend.app.models.user import User
from backend.app.models.variant import Variant, VariantTask
from backend.app.models.tariff import Payment, Tariff
from backend.app.models.teacher import TeacherWithdrawal
from backend.app.crud.payment import cancel_payment, mark_payment_paid, refund_payment

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

ADMIN_COOKIE = "infomir_admin_session"


class AdminLoginPayload(BaseModel):
    login: str
    password: str


class CategoryPayload(BaseModel):
    code: str
    title: str
    exam_type: str
    subject: str = "informatics"
    grade: int | None = None
    description: str | None = None
    sort_order: int = 0


class TestPayload(BaseModel):
    category_id: int | None = None
    grade: int | None = None
    exam_type: str | None = None
    subject: str = "informatics"
    title: str
    question: str
    answer: str
    hint: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    source: str | None = None


class VariantPayload(BaseModel):
    title: str
    exam_type: str
    subject: str = "informatics"
    grade: int | None = None
    description: str | None = None
    time_limit_minutes: int | None = None


class ArticlePayload(BaseModel):
    category_id: int | None = None
    grade: int | None = None
    subject: str = "informatics"
    slug: str
    title: str
    content: str = ""
    content_json: str | None = None
    sort_order: int = 0


class AdminUserPayload(BaseModel):
    role: str
    is_active: bool
    new_password: str | None = Field(default=None, min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_admin_password(cls, value: str | None):
        if value is None:
            return value
        if not (any(ch.islower() for ch in value) and any(ch.isupper() for ch in value) and any(ch.isdigit() for ch in value)):
            raise ValueError("Administrator password must contain lower-case, upper-case and numeric characters")
        return value


class TariffPayload(BaseModel):
    title: str
    price: Decimal = Field(ge=0, decimal_places=2, max_digits=10)
    duration_days: int = Field(gt=0)
    description: str | None = None
    features_json: str | None = None
    is_active: bool = True


class VariantTasksPayload(BaseModel):
    task_ids: list[int]


class WithdrawalStatusPayload(BaseModel):
    status: str
    note: str | None = None


def _audit(db: Session, actor: User, action: str, target_type: str, target_id: int | str, details: dict | None = None) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            details_json=__import__("json").dumps(details or {}, ensure_ascii=False, sort_keys=True),
        )
    )


def _parse_content_blocks(payload: ArticlePayload) -> list[dict]:
    if payload.content_json and payload.content_json.strip():
        try:
            parsed = __import__("json").loads(payload.content_json)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="content_json must be valid JSON") from exc
        if not isinstance(parsed, list) or not all(isinstance(block, dict) for block in parsed):
            raise HTTPException(status_code=400, detail="content_json must be an array of objects")
        return parsed
    return [{"type": "paragraph", "text": line.strip()} for line in payload.content.splitlines() if line.strip()]


def _article_category(db: Session, payload: ArticlePayload) -> TaskCategory:
    category = db.get(TaskCategory, payload.category_id) if payload.category_id else None
    if payload.category_id and not category:
        raise HTTPException(status_code=400, detail="Category not found")
    if not category:
        if payload.grade not in {7, 8, 9}:
            raise HTTPException(status_code=400, detail="Grade 7, 8 or 9 is required for a new article")
        category = TaskCategory(
            code=f"theory_{payload.slug.strip().lower()}",
            title=payload.title.strip(),
            exam_type="oge" if payload.grade == 9 else "vpr",
            subject=payload.subject.strip().lower() or "informatics",
            grade=payload.grade,
            sort_order=payload.sort_order,
        )
        db.add(category)
        db.flush()
    else:
        category.title = payload.title.strip()
        category.sort_order = payload.sort_order
        if payload.grade in {7, 8, 9}:
            category.grade = payload.grade
            category.exam_type = "oge" if payload.grade == 9 else "vpr"
        if payload.subject.strip():
            category.subject = payload.subject.strip().lower()
    return category


def _issue_admin_token(user_id: int, session_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "admin_session",
        "scope": "admin_panel",
        "sv": session_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.admin_session_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_admin_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.InvalidTokenError:
        return None
    if payload.get("scope") != "admin_panel" or payload.get("type") != "admin_session":
        return None
    return payload


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_admin_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid session")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session")
    user = db.get(User, user_id)
    if not user or not user.is_active or (user.role or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if int(payload.get("sv", -1)) != int(user.session_version or 0):
        raise HTTPException(status_code=401, detail="Session has been revoked")
    return user


def build_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin-api", tags=["admin-panel"])

    @router.post("/auth/login")
    def admin_login(payload: AdminLoginPayload, request: Request, response: Response, db: Session = Depends(get_db)):
        login = payload.login.strip().lower()
        rate_limiter.check(client_key(request, "admin-login", login), limit=5, window_seconds=300)
        admin = db.execute(select(User).where(func.lower(User.email) == login)).scalar_one_or_none()
        if not admin or not admin.is_active or (admin.role or "").strip().lower() != "admin":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        verified, replacement_hash = verify_and_update_password(payload.password, admin.password_hash)
        if not verified:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if replacement_hash:
            admin.password_hash = replacement_hash
            db.add(admin)
            db.commit()
            db.refresh(admin)

        token = _issue_admin_token(admin.id, int(admin.session_version or 0))
        response.set_cookie(
            key=ADMIN_COOKIE,
            value=token,
            httponly=True,
            secure=settings.app_env == "production",
            samesite="strict",
            max_age=settings.admin_session_expire_minutes * 60,
            path="/",
        )
        return {"ok": True, "admin": {"id": admin.id, "name": admin.name, "email": admin.email}}

    @router.post("/auth/logout")
    def admin_logout(request: Request, response: Response, db: Session = Depends(get_db)):
        token = request.cookies.get(ADMIN_COOKIE)
        payload = _decode_admin_token(token) if token else None
        if payload:
            try:
                user = db.get(User, int(payload.get("sub")))
            except (TypeError, ValueError):
                user = None
            if user and int(payload.get("sv", -1)) == int(user.session_version or 0):
                user.session_version = int(user.session_version or 0) + 1
                db.add(user)
                db.commit()
        response.delete_cookie(ADMIN_COOKIE, path="/")
        return {"ok": True}

    @router.get("/auth/me")
    def admin_me(admin: User = Depends(get_current_admin)):
        return {"id": admin.id, "name": admin.name, "email": admin.email}

    @router.get("/users")
    def list_users(role: str | None = None, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        stmt = select(User).order_by(User.id.asc())
        if role:
            stmt = stmt.where(User.role == role)
        rows = db.execute(stmt).scalars().all()
        return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "grade": u.grade, "is_active": u.is_active} for u in rows]

    @router.patch("/users/{user_id}")
    def update_user(
        user_id: int,
        payload: AdminUserPayload,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        if payload.role not in {"student", "teacher", "admin"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        item = db.get(User, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="User not found")
        if item.id == admin.id and (payload.role != "admin" or not payload.is_active):
            raise HTTPException(status_code=400, detail="You cannot remove your own administrator access")
        if payload.role == "admin" and item.role != "admin" and not payload.new_password:
            raise HTTPException(status_code=400, detail="A new 12-character password is required when promoting an administrator")
        item.role = payload.role
        item.is_active = payload.is_active
        if payload.new_password:
            item.password_hash = hash_password(payload.new_password)
        item.session_version = int(item.session_version or 0) + 1
        _audit(db, admin, "user.access_updated", "user", item.id, {"role": payload.role, "is_active": payload.is_active})
        db.commit()
        return {"ok": True}

    @router.get("/categories")
    def list_categories(subject: str | None = None, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        stmt = select(TaskCategory).order_by(TaskCategory.sort_order.asc(), TaskCategory.id.asc())
        if subject is not None:
            stmt = stmt.where(TaskCategory.subject == subject)
        rows = db.execute(stmt).scalars().all()
        return [{"id": c.id, "code": c.code, "title": c.title, "exam_type": c.exam_type, "subject": c.subject, "grade": c.grade, "description": c.description, "sort_order": c.sort_order} for c in rows]

    @router.post("/categories")
    def create_category(payload: CategoryPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = TaskCategory(**payload.model_dump())
        db.add(item); db.commit(); db.refresh(item)
        return {"id": item.id}

    @router.put("/categories/{category_id}")
    def update_category(category_id: int, payload: CategoryPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(TaskCategory, category_id)
        if not item: raise HTTPException(status_code=404, detail="Category not found")
        for k, v in payload.model_dump().items(): setattr(item, k, v)
        db.add(item); db.commit();
        return {"ok": True}

    @router.delete("/categories/{category_id}")
    def delete_category(category_id: int, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(TaskCategory, category_id)
        if not item: raise HTTPException(status_code=404, detail="Category not found")
        db.delete(item); db.commit();
        return {"ok": True}

    @router.get("/tests")
    def list_tests(grade: int | None = None, subject: str | None = None, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        stmt = select(Task).order_by(Task.id.desc()).limit(500)
        if grade is not None:
            stmt = stmt.where(Task.grade == grade)
        if subject is not None:
            stmt = stmt.where(Task.subject == subject)
        rows = db.execute(stmt).scalars().all()
        return [{"id": t.id, "category_id": t.category_id, "grade": t.grade, "exam_type": t.exam_type, "subject": t.subject, "title": t.title, "question": t.question, "answer": t.answer, "hint": t.hint, "explanation": t.explanation, "difficulty": t.difficulty, "source": t.source} for t in rows]

    @router.post("/tests")
    def create_test(payload: TestPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = Task(**payload.model_dump())
        db.add(item); db.commit(); db.refresh(item)
        return {"id": item.id}

    @router.put("/tests/{test_id}")
    def update_test(test_id: int, payload: TestPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(Task, test_id)
        if not item: raise HTTPException(status_code=404, detail="Test not found")
        for k, v in payload.model_dump().items(): setattr(item, k, v)
        db.add(item); db.commit();
        return {"ok": True}

    @router.delete("/tests/{test_id}")
    def delete_test(test_id: int, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(Task, test_id)
        if not item: raise HTTPException(status_code=404, detail="Test not found")
        used = db.execute(select(AttemptAnswer.id).where(AttemptAnswer.task_id == test_id).limit(1)).scalar_one_or_none()
        if used is not None:
            raise HTTPException(status_code=409, detail="The task has attempt history and cannot be deleted")
        db.delete(item); db.commit();
        return {"ok": True}

    @router.get("/variants")
    def list_variants(grade: int | None = None, subject: str | None = None, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        stmt = select(Variant).order_by(Variant.id.desc()).limit(300)
        if grade is not None:
            stmt = stmt.where(Variant.grade == grade)
        if subject is not None:
            stmt = stmt.where(Variant.subject == subject)
        rows = db.execute(stmt).scalars().all()
        result = []
        for v in rows:
            task_ids = list(
                db.execute(
                    select(VariantTask.task_id)
                    .where(VariantTask.variant_id == v.id)
                    .order_by(VariantTask.sort_order.asc())
                ).scalars().all()
            )
            result.append({"id": v.id, "title": v.title, "exam_type": v.exam_type, "subject": v.subject, "grade": v.grade, "description": v.description, "time_limit_minutes": v.time_limit_minutes, "task_ids": task_ids})
        return result

    @router.post("/variants")
    def create_variant(payload: VariantPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = Variant(**payload.model_dump())
        db.add(item); db.commit(); db.refresh(item)
        return {"id": item.id}

    @router.put("/variants/{variant_id}")
    def update_variant(variant_id: int, payload: VariantPayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(Variant, variant_id)
        if not item: raise HTTPException(status_code=404, detail="Variant not found")
        for k, v in payload.model_dump().items(): setattr(item, k, v)
        db.add(item); db.commit();
        return {"ok": True}

    @router.delete("/variants/{variant_id}")
    def delete_variant(variant_id: int, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(Variant, variant_id)
        if not item: raise HTTPException(status_code=404, detail="Variant not found")
        db.delete(item); db.commit();
        return {"ok": True}

    @router.put("/variants/{variant_id}/tasks")
    def update_variant_tasks(
        variant_id: int,
        payload: VariantTasksPayload,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        variant = db.get(Variant, variant_id)
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        task_ids = list(dict.fromkeys(int(item) for item in payload.task_ids))
        tasks = list(db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()) if task_ids else []
        if len(tasks) != len(task_ids):
            raise HTTPException(status_code=400, detail="One or more tasks do not exist")
        for task in tasks:
            if task.grade != variant.grade or task.exam_type != variant.exam_type or task.subject != variant.subject:
                raise HTTPException(status_code=400, detail=f"Task {task.id} does not match the variant")
        existing = list(db.execute(select(VariantTask).where(VariantTask.variant_id == variant.id)).scalars().all())
        for row in existing:
            db.delete(row)
        for index, task_id in enumerate(task_ids, start=1):
            db.add(VariantTask(variant_id=variant.id, task_id=task_id, sort_order=index, points=1))
        db.commit()
        return {"ok": True, "task_ids": task_ids}


    @router.get("/tariffs")
    def list_tariffs(_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        rows = db.execute(select(Tariff).order_by(Tariff.id.asc())).scalars().all()
        return [{
            "id": t.id,
            "code": t.code,
            "title": t.title,
            "price": float(t.price or 0),
            "duration_days": int(t.duration_days),
            "description": t.description,
            "features_json": t.features_json,
            "is_active": t.is_active,
        } for t in rows]

    @router.put("/tariffs/{tariff_id}")
    def update_tariff(
        tariff_id: int,
        payload: TariffPayload,
        _admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        item = db.get(Tariff, tariff_id)
        if not item:
            raise HTTPException(status_code=404, detail="Tariff not found")
        if payload.features_json:
            try:
                features = __import__("json").loads(payload.features_json)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="features_json must be valid JSON") from exc
            if not isinstance(features, list) or not all(isinstance(value, str) for value in features):
                raise HTTPException(status_code=400, detail="features_json must be an array of strings")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        db.commit()
        return {"ok": True}

    @router.get("/payments")
    def list_admin_payments(
        status: str | None = None,
        _admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        stmt = select(Payment).order_by(Payment.id.desc()).limit(500)
        if status:
            stmt = stmt.where(Payment.status == status)
        rows = db.execute(stmt).scalars().all()
        result = []
        for payment in rows:
            user = db.get(User, payment.user_id)
            tariff = db.get(Tariff, payment.tariff_id)
            result.append({"id": payment.id, "user_id": payment.user_id, "user_email": user.email if user else None, "tariff_id": payment.tariff_id, "tariff_title": tariff.title if tariff else None, "amount": float(payment.amount), "status": payment.status, "provider": payment.provider, "created_at": payment.created_at.isoformat() if payment.created_at else None})
        return result

    @router.post("/payments/{payment_id}/mark-paid")
    def admin_mark_payment_paid(
        payment_id: int,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        try:
            payment = mark_payment_paid(db, payment_id=payment_id, external_id=f"manual-{payment_id}")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit(db, admin, "payment.mark_paid", "payment", payment.id, {"status": payment.status})
        db.commit()
        return {"ok": True, "status": payment.status}

    @router.post("/payments/{payment_id}/refund")
    def admin_refund_payment(
        payment_id: int,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        try:
            payment = refund_payment(db, payment_id=payment_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit(db, admin, "payment.refund", "payment", payment.id, {"status": payment.status})
        db.commit()
        return {"ok": True, "status": payment.status}

    @router.post("/payments/{payment_id}/cancel")
    def admin_cancel_payment(
        payment_id: int,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        try:
            payment = cancel_payment(db, payment_id=payment_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit(db, admin, "payment.cancel", "payment", payment.id, {"status": payment.status})
        db.commit()
        return {"ok": True, "status": payment.status}

    @router.get("/withdrawals")
    def list_withdrawals(_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        rows = db.execute(select(TeacherWithdrawal).order_by(TeacherWithdrawal.id.desc()).limit(500)).scalars().all()
        result = []
        for row in rows:
            teacher = db.get(User, row.teacher_id)
            result.append({"id": row.id, "teacher_id": row.teacher_id, "teacher_email": teacher.email if teacher else None, "amount": float(row.amount), "status": row.status, "note": row.note, "created_at": row.created_at.isoformat() if row.created_at else None})
        return result

    @router.get("/audit-logs")
    def list_audit_logs(_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        rows = db.execute(select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(500)).scalars().all()
        return [
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "details_json": row.details_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @router.patch("/withdrawals/{withdrawal_id}")
    def update_withdrawal(
        withdrawal_id: int,
        payload: WithdrawalStatusPayload,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ):
        if payload.status not in {"requested", "processing", "paid", "rejected"}:
            raise HTTPException(status_code=400, detail="Invalid withdrawal status")
        row = db.get(TeacherWithdrawal, withdrawal_id)
        if not row:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        transitions = {
            "requested": {"processing", "paid", "rejected"},
            "processing": {"paid", "rejected"},
            "paid": set(),
            "rejected": set(),
        }
        if payload.status != row.status and payload.status not in transitions.get(row.status, set()):
            raise HTTPException(status_code=409, detail=f"Cannot change withdrawal from {row.status} to {payload.status}")
        row.status = payload.status
        row.note = payload.note
        _audit(db, admin, "withdrawal.status_updated", "teacher_withdrawal", row.id, {"status": payload.status})
        db.commit()
        return {"ok": True}

    @router.get("/articles")
    def list_articles(grade: int | None = None, subject: str | None = None, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        rows = db.execute(select(TheoryTopic).order_by(TheoryTopic.id.desc()).limit(400)).scalars().all()
        result = []
        for a in rows:
            if grade is not None and a.category_grade is not None and int(a.category_grade) != int(grade):
                continue
            if subject is not None and a.category_subject is not None and str(a.category_subject) != str(subject):
                continue
            title = a.category_title or a.slug
            content = ""
            if isinstance(a.content_json, list):
                parts = [str(block.get("text") or "").strip() for block in a.content_json if isinstance(block, dict)]
                content = "\n".join([p for p in parts if p])
            result.append({"id": a.id, "category_id": a.category_id, "slug": a.slug, "title": title, "content": content, "content_json": __import__("json").dumps(a.content_json or [], ensure_ascii=False, indent=2), "sort_order": a.sort_order, "grade": a.category_grade, "subject": a.category_subject})
        return result

    @router.post("/articles")
    def create_article(payload: ArticlePayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        blocks = _parse_content_blocks(payload)
        category = _article_category(db, payload)
        item = TheoryTopic(category_id=category.id, slug=payload.slug, content_json=blocks, sort_order=payload.sort_order)
        db.add(item); db.commit(); db.refresh(item)
        return {"id": item.id}

    @router.put("/articles/{article_id}")
    def update_article(article_id: int, payload: ArticlePayload, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(TheoryTopic, article_id)
        if not item: raise HTTPException(status_code=404, detail="Article not found")
        blocks = _parse_content_blocks(payload)
        category = _article_category(db, payload)
        item.category_id = category.id
        item.slug = payload.slug
        item.content_json = blocks
        item.sort_order = payload.sort_order
        db.add(item); db.commit();
        return {"ok": True}

    @router.delete("/articles/{article_id}")
    def delete_article(article_id: int, _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
        item = db.get(TheoryTopic, article_id)
        if not item: raise HTTPException(status_code=404, detail="Article not found")
        db.delete(item); db.commit();
        return {"ok": True}

    return router


def create_admin_app() -> FastAPI:
    app = FastAPI(title="Infomir Admin", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def protect_admin_requests(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > settings.max_request_body_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        if (
            request.url.path.startswith("/admin-api/")
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("x-requested-with") != "InfomirAdmin"
        ):
            return JSONResponse({"detail": "Missing request verification header"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/login")

    @app.get("/login", include_in_schema=False)
    def login_page():
        return FileResponse(TEMPLATES_DIR / "admin" / "login.html")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard_page():
        return FileResponse(TEMPLATES_DIR / "admin" / "dashboard.html")

    @app.get("/health")
    def health(db: Session = Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "app": "admin", "database": "ok"}

    app.include_router(build_admin_router())
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR, html=True), name="templates")
    return app
