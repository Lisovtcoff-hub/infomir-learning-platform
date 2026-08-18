from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import secrets

from sqlalchemy import func as sa_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import settings
from backend.app.models.tariff import Payment, Tariff, TeacherCommission, UserSubscription
from backend.app.models.teacher import TeacherGroup, TeacherGroupMember, TeacherProfile, TeacherWithdrawal
from backend.app.models.user import User


MONEY_QUANT = Decimal("0.01")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_payment(
    db: Session,
    *,
    user: User,
    tariff_code: str,
    idempotency_key: str | None = None,
) -> Payment:
    if str(user.role or "").strip().lower() != "student":
        raise ValueError("Only student accounts can purchase a tariff")
    tariff = db.execute(
        select(Tariff).where(Tariff.code == tariff_code, Tariff.is_active.is_(True))
    ).scalar_one_or_none()
    if not tariff:
        raise ValueError("Tariff not found")
    if Decimal(tariff.price or 0) <= 0:
        raise ValueError("The free tariff does not require a payment")

    key = (idempotency_key or secrets.token_hex(16)).strip().lower()
    existing = db.execute(select(Payment).where(Payment.idempotency_key == key)).scalar_one_or_none()
    if existing:
        if existing.user_id != user.id or existing.tariff_id != tariff.id:
            raise ValueError("Idempotency key is already used for another payment")
        return existing

    payment = Payment(
        user_id=user.id,
        tariff_id=tariff.id,
        amount=Decimal(tariff.price).quantize(MONEY_QUANT),
        provider=settings.payment_provider,
        idempotency_key=key,
        status="pending",
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.execute(select(Payment).where(Payment.idempotency_key == key)).scalar_one_or_none()
        if existing and existing.user_id == user.id and existing.tariff_id == tariff.id:
            return existing
        raise ValueError("Could not create an idempotent payment") from exc
    db.refresh(payment)
    return payment


def list_user_payments(db: Session, *, user_id: int) -> list[Payment]:
    return list(
        db.execute(
            select(Payment)
            .options(selectinload(Payment.tariff))
            .where(Payment.user_id == user_id)
            .order_by(Payment.id.desc())
            .limit(100)
        ).scalars().all()
    )


def list_payments(db: Session, *, status: str | None = None) -> list[Payment]:
    stmt = select(Payment).options(selectinload(Payment.tariff)).order_by(Payment.id.desc()).limit(500)
    if status:
        stmt = stmt.where(Payment.status == status)
    return list(db.execute(stmt).scalars().all())


def mark_payment_paid(
    db: Session,
    *,
    payment_id: int,
    external_id: str | None = None,
) -> Payment:
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).scalar_one_or_none()
    if not payment:
        raise LookupError("Payment not found")
    if payment.status == "paid":
        return payment
    if payment.status != "pending":
        raise ValueError(f"Payment in status '{payment.status}' cannot be completed")

    tariff = db.get(Tariff, payment.tariff_id)
    user = db.get(User, payment.user_id)
    if not tariff or not user or not user.is_active:
        raise ValueError("Payment user or tariff is unavailable")
    if Decimal(payment.amount) != Decimal(tariff.price):
        raise ValueError("Payment amount does not match the tariff price")

    now = utc_now()
    current_expiry = user.paid_tariff_expires_at
    if current_expiry and current_expiry.tzinfo is None:
        current_expiry = current_expiry.replace(tzinfo=timezone.utc)
    base = current_expiry if current_expiry and current_expiry > now else now
    expires_at = base + timedelta(days=int(tariff.duration_days))

    payment.status = "paid"
    payment.external_id = external_id or payment.external_id
    payment.paid_at = now
    user.paid_tariff_id = tariff.id
    user.paid_tariff_expires_at = expires_at
    db.add(
        UserSubscription(
            user_id=user.id,
            tariff_id=tariff.id,
            payment_id=payment.id,
            started_at=now,
            expires_at=expires_at,
            status="active",
        )
    )

    teacher_id = db.execute(
        select(TeacherGroup.teacher_id)
        .join(TeacherGroupMember, TeacherGroupMember.group_id == TeacherGroup.id)
        .where(TeacherGroupMember.student_id == user.id)
        .limit(1)
    ).scalar_one_or_none()
    if teacher_id is not None:
        profile = db.get(TeacherProfile, int(teacher_id))
        commission_percent = Decimal(
            profile.commission_percent if profile else settings.teacher_commission_percent
        )
        commission_amount = (
            Decimal(payment.amount) * commission_percent / Decimal("100")
        ).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if commission_amount > 0:
            db.add(
                TeacherCommission(
                    teacher_id=int(teacher_id),
                    student_id=user.id,
                    payment_id=payment.id,
                    amount=commission_amount,
                    commission_percent=commission_percent,
                    status="available",
                )
            )

    db.add(payment)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent = db.get(Payment, payment_id)
        if concurrent and concurrent.status == "paid":
            return concurrent
        raise ValueError("Payment confirmation conflicted with another operation") from exc
    db.refresh(payment)
    return payment


def refund_payment(db: Session, *, payment_id: int) -> Payment:
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).scalar_one_or_none()
    if not payment:
        raise LookupError("Payment not found")
    if payment.status == "refunded":
        return payment
    if payment.status != "paid":
        raise ValueError("Only a paid payment can be refunded")

    payment.status = "refunded"
    subscription = db.execute(
        select(UserSubscription).where(UserSubscription.payment_id == payment.id)
    ).scalar_one_or_none()
    if subscription:
        subscription.status = "cancelled"

    commission = db.execute(
        select(TeacherCommission).where(TeacherCommission.payment_id == payment.id)
    ).scalar_one_or_none()
    if commission:
        active_withdrawal = db.execute(
            select(TeacherWithdrawal.id)
            .where(
                TeacherWithdrawal.teacher_id == commission.teacher_id,
                TeacherWithdrawal.status.in_(["requested", "processing"]),
            )
            .limit(1)
        ).scalar_one_or_none()
        if active_withdrawal is not None:
            raise ValueError("Reject or complete the teacher's pending withdrawal before refunding this payment")
        paid_withdrawals = Decimal(
            db.execute(
                select(sa_func.coalesce(sa_func.sum(TeacherWithdrawal.amount), 0)).where(
                    TeacherWithdrawal.teacher_id == commission.teacher_id,
                    TeacherWithdrawal.status == "paid",
                )
            ).scalar_one()
            or 0
        )
        other_available = Decimal(
            db.execute(
                select(sa_func.coalesce(sa_func.sum(TeacherCommission.amount), 0)).where(
                    TeacherCommission.teacher_id == commission.teacher_id,
                    TeacherCommission.status == "available",
                    TeacherCommission.id != commission.id,
                )
            ).scalar_one()
            or 0
        )
        if paid_withdrawals > other_available:
            raise ValueError("This commission has already funded a paid teacher withdrawal")
        commission.status = "reversed"

    user = db.get(User, payment.user_id)
    if user and subscription:
        db.flush()
        latest = db.execute(
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user.id,
                UserSubscription.status == "active",
                UserSubscription.id != subscription.id,
            )
            .order_by(UserSubscription.expires_at.desc(), UserSubscription.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        latest_expiry = latest.expires_at if latest else None
        if latest_expiry and latest_expiry.tzinfo is None:
            latest_expiry = latest_expiry.replace(tzinfo=timezone.utc)
        if latest and (latest_expiry is None or latest_expiry > utc_now()):
            user.paid_tariff_id = latest.tariff_id
            user.paid_tariff_expires_at = latest.expires_at
        else:
            free = db.execute(select(Tariff).where(Tariff.code == "free")).scalar_one_or_none()
            user.paid_tariff_id = free.id if free else None
            user.paid_tariff_expires_at = None

    db.commit()
    db.refresh(payment)
    return payment


def cancel_payment(db: Session, *, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise LookupError("Payment not found")
    if payment.status == "cancelled":
        return payment
    if payment.status != "pending":
        raise ValueError("Only a pending payment can be cancelled")
    payment.status = "cancelled"
    db.commit()
    db.refresh(payment)
    return payment
