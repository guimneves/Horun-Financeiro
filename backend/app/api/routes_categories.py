from __future__ import annotations

from fastapi import APIRouter

from app.db.models.budget import EXPENSE_CATEGORIES
from app.schemas.budget import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories():
    return [
        CategoryOut(code=code, label=meta["label"], group=meta["group"], is_personnel=meta["is_personnel"])
        for code, meta in EXPENSE_CATEGORIES.items()
    ]
