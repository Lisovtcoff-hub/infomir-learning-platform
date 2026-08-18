from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.rate_limit import client_key, rate_limiter
from backend.app.crud.payment import create_payment, list_user_payments, mark_payment_paid
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.payment import PaymentCreate, PaymentRead


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def start_payment(
    payload: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limiter.check(client_key(request, "payment-create", str(current_user.id)), limit=10, window_seconds=60)
    try:
        payment = create_payment(
            db,
            user=current_user,
            tariff_code=payload.tariff_code.strip().lower(),
            idempotency_key=payload.idempotency_key,
        )
        return PaymentRead.model_validate(payment).model_copy(
            update={"payment_instructions": settings.manual_payment_instructions if payment.provider == "manual" else None}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/my", response_model=list[PaymentRead])
def my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_user_payments(db, user_id=current_user.id)


@router.post("/{payment_id}/dev-confirm", response_model=PaymentRead)
def dev_confirm_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.enable_dev_payment_confirmation or settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    payment = next((item for item in list_user_payments(db, user_id=current_user.id) if item.id == payment_id), None)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        return mark_payment_paid(db, payment_id=payment.id, external_id=f"dev-{payment.id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
