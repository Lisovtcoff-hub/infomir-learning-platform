from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.crud.tariff import get_tariffs
from backend.app.db.session import get_db
from backend.app.schemas.tariff import TariffRead

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("/", response_model=list[TariffRead])
def list_tariffs(db: Session = Depends(get_db)):
    return get_tariffs(db)
