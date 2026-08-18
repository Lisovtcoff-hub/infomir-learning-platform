from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    tariff_code: str = Field(min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=64)


class PaymentRead(BaseModel):
    id: int
    user_id: int
    tariff_id: int
    amount: Decimal
    currency: str
    status: str
    provider: str
    external_id: str | None
    paid_at: datetime | None
    created_at: datetime
    payment_instructions: str | None = None

    model_config = ConfigDict(from_attributes=True)
