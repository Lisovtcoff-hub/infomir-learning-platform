from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.crud.variant import get_variant_with_tasks, get_variants
from backend.app.api.deps import get_current_user
from backend.app.core.entitlements import has_feature
from backend.app.db.session import get_db
from backend.app.schemas.variant import VariantDetailRead, VariantRead
from backend.app.models.user import User

router = APIRouter(prefix="/variants", tags=["variants"])


@router.get("/", response_model=list[VariantRead])
def list_variants(
    grade: int | None = None,
    exam_type: str | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
):
    return get_variants(db, grade=grade, exam_type=exam_type, subject=subject)


@router.get("/{variant_id}", response_model=VariantDetailRead)
def retrieve_variant(
    variant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_feature(current_user, "variants"):
        raise HTTPException(status_code=402, detail="A tariff with exam variants is required")
    variant = get_variant_with_tasks(db, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant
