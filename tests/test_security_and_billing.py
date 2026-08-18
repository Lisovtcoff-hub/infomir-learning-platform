from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from backend.app.core.security import hash_password
from backend.app.crud.user import create_user, ensure_teacher_profile
from backend.app.db.session import SessionLocal
from backend.app.models.tariff import Tariff, TeacherCommission
from backend.app.models.audit import AdminAuditLog
from backend.app.models.attempt import Attempt
from backend.app.models.task import Task
from backend.app.models.teacher import TeacherGroup
from backend.app.models.user import User
from backend.app.models.variant import Variant, VariantTask
from backend.app.schemas.user import UserCreate


def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def make_user(*, role: str = "student", grade: int | None = 8, password: str = "Password123") -> tuple[User, str]:
    email = unique_email(role)
    with SessionLocal() as db:
        user = create_user(
            db,
            UserCreate(name=f"Test {role}", email=email, password=password, grade=grade),
            role=role,
        )
        user_id = user.id
    with SessionLocal() as db:
        return db.get(User, user_id), password


def login(client, email: str, password: str = "Password123"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}


def ensure_admin() -> tuple[User, str]:
    password = "AdminPassword123"
    email = unique_email("admin")
    with SessionLocal() as db:
        free = db.execute(select(Tariff).where(Tariff.code == "free")).scalar_one()
        admin = User(
            name="Test administrator",
            email=email,
            password_hash=hash_password(password),
            role="admin",
            grade=None,
            paid_tariff_id=free.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
    with SessionLocal() as db:
        return db.get(User, admin_id), password


def test_public_tasks_do_not_expose_answer_and_check_requires_login(public_client):
    response = public_client.get("/api/tasks", params={"grade": 8, "exam_type": "vpr"})
    assert response.status_code == 200
    tasks = response.json()
    assert tasks
    assert "answer" not in tasks[0]
    assert "correct_answer" not in tasks[0]

    checked = public_client.post(
        f"/api/tasks/{tasks[0]['id']}/check",
        json={"user_answer": "anything"},
    )
    assert checked.status_code == 401


def test_health_hosts_and_security_headers(public_client, admin_client):
    public_health = public_client.get("/api/health")
    assert public_health.json() == {"status": "ok", "database": "ok"}
    assert public_health.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in public_health.headers["content-security-policy"]

    admin_health = admin_client.get("/health")
    assert admin_health.json()["database"] == "ok"
    assert admin_health.headers["x-frame-options"] == "DENY"

    invalid = public_client.get("/api/health", headers={"Host": "attacker.example"})
    assert invalid.status_code == 400


def test_user_cannot_assign_a_paid_tariff(public_client):
    user, password = make_user()
    login(public_client, user.email, password)
    response = public_client.patch("/api/users/me/tariff", json={"tariff_code": "optimum"})
    assert response.status_code == 410


def test_free_and_full_content_entitlements(public_client):
    guest_theory = public_client.get("/api/theory", params={"grade": 8, "subject": "informatics"})
    assert guest_theory.status_code == 200
    assert len(guest_theory.json()) == 3
    guest_tasks = public_client.get("/api/tasks", params={"grade": 8, "exam_type": "vpr"})
    assert guest_tasks.status_code == 200
    assert guest_tasks.json()
    assert {row["difficulty"] for row in guest_tasks.json()} == {"easy"}

    user, password = make_user()
    login(public_client, user.email, password)
    with SessionLocal() as db:
        medium_task = db.execute(
            select(Task).where(Task.grade == 8, Task.difficulty == "medium").limit(1)
        ).scalar_one()
        medium_task_id = medium_task.id
    assert public_client.get(f"/api/tasks/{medium_task_id}").status_code == 402

    with SessionLocal() as db:
        user_db = db.get(User, user.id)
        base = db.execute(select(Tariff).where(Tariff.code == "base")).scalar_one()
        user_db.paid_tariff_id = base.id
        db.commit()
    assert public_client.get(f"/api/tasks/{medium_task_id}").status_code == 200
    full_theory = public_client.get("/api/theory", params={"grade": 8, "subject": "informatics"})
    assert len(full_theory.json()) > 3


def test_attempts_are_owner_only(public_client):
    owner, password = make_user()
    login(public_client, owner.email, password)
    attempt = public_client.post("/api/attempts", json={"mode": "practice", "variant_id": None})
    assert attempt.status_code == 200
    attempt_id = attempt.json()["id"]

    other, other_password = make_user()
    public_client.post("/api/auth/logout")
    login(public_client, other.email, other_password)
    with SessionLocal() as db:
        task_id = db.execute(select(Task.id).where(Task.grade == 8).limit(1)).scalar_one()
    response = public_client.post(
        f"/api/attempts/{attempt_id}/answers",
        json={"task_id": task_id, "user_answer": "8"},
    )
    assert response.status_code == 404
    assert public_client.post(f"/api/attempts/{attempt_id}/finish").status_code == 404


def test_practice_attempt_cannot_smuggle_a_paid_variant(public_client):
    user, password = make_user()
    with SessionLocal() as db:
        variant_id = db.execute(select(Variant.id).where(Variant.grade == 8).limit(1)).scalar_one()
    login(public_client, user.email, password)
    response = public_client.post("/api/attempts", json={"mode": "practice", "variant_id": variant_id})
    assert response.status_code == 422


def test_variant_time_limit_is_enforced_by_the_api(public_client):
    user, password = make_user()
    with SessionLocal() as db:
        user_db = db.get(User, user.id)
        optimum = db.execute(select(Tariff).where(Tariff.code == "optimum")).scalar_one()
        user_db.paid_tariff_id = optimum.id
        variant = db.execute(select(Variant).where(Variant.grade == 8).limit(1)).scalar_one()
        task_id = db.execute(select(VariantTask.task_id).where(VariantTask.variant_id == variant.id).limit(1)).scalar_one()
        variant_id = variant.id
        db.commit()
    login(public_client, user.email, password)
    started = public_client.post("/api/attempts", json={"mode": "variant", "variant_id": variant_id})
    attempt_id = started.json()["id"]
    with SessionLocal() as db:
        attempt = db.get(Attempt, attempt_id)
        attempt.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        db.commit()
    response = public_client.post(
        f"/api/attempts/{attempt_id}/answers",
        json={"task_id": task_id, "user_answer": "test"},
    )
    assert response.status_code == 400
    assert "time limit" in response.json()["detail"].lower()


def test_password_change_revokes_existing_session_and_uses_argon2(public_client):
    user, password = make_user()
    login(public_client, user.email, password)
    changed = public_client.patch(
        "/api/users/me/password",
        json={"old_password": password, "new_password": "NewPassword456"},
    )
    assert changed.status_code == 200
    assert public_client.get("/api/users/me").status_code == 401
    login(public_client, user.email, "NewPassword456")
    with SessionLocal() as db:
        updated = db.get(User, user.id)
        assert updated.password_hash.startswith("$argon2")


def test_legacy_public_admin_api_is_not_exposed(public_client):
    assert public_client.get("/api/admin/me").status_code == 404


def test_variant_scores_all_tasks_and_reveals_solutions_only_after_finish(public_client):
    user, password = make_user()
    with SessionLocal() as db:
        user_db = db.get(User, user.id)
        optimum = db.execute(select(Tariff).where(Tariff.code == "optimum")).scalar_one()
        user_db.paid_tariff_id = optimum.id
        db.commit()
        variant = db.execute(select(Variant).where(Variant.grade == 8).limit(1)).scalar_one()
        task_id = db.execute(
            select(VariantTask.task_id)
            .where(VariantTask.variant_id == variant.id)
            .order_by(VariantTask.sort_order)
            .limit(1)
        ).scalar_one()
        task = db.get(Task, task_id)
        variant_id = variant.id
        correct_answer = task.answer
        expected_total = db.execute(
            select(func.sum(VariantTask.points)).where(VariantTask.variant_id == variant.id)
        ).scalar_one()

    login(public_client, user.email, password)
    started = public_client.post("/api/attempts", json={"mode": "variant", "variant_id": variant_id})
    assert started.status_code == 200, started.text
    attempt_id = started.json()["id"]
    assert public_client.get(f"/api/attempts/{attempt_id}/result").status_code == 409

    saved = public_client.post(
        f"/api/attempts/{attempt_id}/answers",
        json={"task_id": task_id, "user_answer": correct_answer},
    )
    assert saved.status_code == 200
    assert "is_correct" not in saved.json()
    finished = public_client.post(f"/api/attempts/{attempt_id}/finish")
    assert finished.status_code == 200
    assert finished.json()["score"] == 1
    assert finished.json()["max_score"] == int(expected_total)

    result = public_client.get(f"/api/attempts/{attempt_id}/result")
    assert result.status_code == 200
    rows = result.json()["answers"]
    assert len(rows) == int(expected_total)
    assert next(row for row in rows if row["task_id"] == task_id)["correct_answer"] == correct_answer


def test_payment_activates_subscription_and_teacher_commission(public_client, admin_client):
    teacher, teacher_password = make_user(role="teacher", grade=None)
    with SessionLocal() as db:
        profile = ensure_teacher_profile(db, teacher.id)
        db.add(TeacherGroup(teacher_id=teacher.id, title="Main group"))
        db.commit()
        invite_code = profile.invite_code

    student, student_password = make_user()
    login(public_client, student.email, student_password)
    connected = public_client.post("/api/users/me/teacher", json={"invite_code": invite_code})
    assert connected.status_code == 200, connected.text
    created = public_client.post(
        "/api/payments",
        json={"tariff_code": "optimum", "idempotency_key": uuid4().hex},
    )
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    admin, admin_password = ensure_admin()
    signed_in = admin_client.post(
        "/admin-api/auth/login",
        json={"login": admin.email, "password": admin_password},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert signed_in.status_code == 200, signed_in.text
    confirmed = admin_client.post(
        f"/admin-api/payments/{payment_id}/mark-paid",
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert confirmed.status_code == 200, confirmed.text

    me = public_client.get("/api/users/me")
    assert me.json()["paid_tariff_code"] == "optimum"
    assert me.json()["paid_tariff_expires_at"]
    with SessionLocal() as db:
        commission = db.execute(
            select(TeacherCommission).where(TeacherCommission.payment_id == payment_id)
        ).scalar_one()
        assert commission.teacher_id == teacher.id
        assert commission.amount == Decimal("119.80")
        assert commission.commission_percent == Decimal("20.00")

    public_client.post("/api/auth/logout")
    login(public_client, teacher.email, teacher_password)
    first_withdrawal = public_client.post("/api/teacher/withdrawals")
    assert first_withdrawal.status_code == 201, first_withdrawal.text
    withdrawal_id = first_withdrawal.json()["id"]
    assert public_client.post("/api/teacher/withdrawals").status_code == 409

    paid = admin_client.patch(
        f"/admin-api/withdrawals/{withdrawal_id}",
        json={"status": "paid", "note": "test payout"},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert paid.status_code == 200, paid.text
    refund = admin_client.post(
        f"/admin-api/payments/{payment_id}/refund",
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert refund.status_code == 400
    with SessionLocal() as db:
        assert db.execute(select(func.count(AdminAuditLog.id))).scalar_one() >= 2


def test_no_default_admin_credentials(admin_client):
    response = admin_client.post(
        "/admin-api/auth/login",
        json={"login": "admin", "password": "admin"},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert response.status_code == 401


def test_admin_promotion_requires_a_new_strong_password(admin_client):
    target, _password = make_user()
    admin, admin_password = ensure_admin()
    signed_in = admin_client.post(
        "/admin-api/auth/login",
        json={"login": admin.email, "password": admin_password},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert signed_in.status_code == 200
    missing_password = admin_client.patch(
        f"/admin-api/users/{target.id}",
        json={"role": "admin", "is_active": True},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert missing_password.status_code == 400
    promoted = admin_client.patch(
        f"/admin-api/users/{target.id}",
        json={"role": "admin", "is_active": True, "new_password": "StrongAdminPassword123"},
        headers={"X-Requested-With": "InfomirAdmin"},
    )
    assert promoted.status_code == 200
    with SessionLocal() as db:
        updated = db.get(User, target.id)
        assert updated.role == "admin"
        assert updated.password_hash.startswith("$argon2")
