from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tariff import Tariff


def get_tariffs(db: Session) -> list[Tariff]:
    return list(db.execute(select(Tariff).where(Tariff.is_active == True).order_by(Tariff.id)).scalars().all())


def get_tariff_by_code(db: Session, code: str) -> Tariff | None:
    return db.execute(select(Tariff).where(Tariff.code == code)).scalar_one_or_none()
