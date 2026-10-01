from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core.money import Money, NonNegativeQuantity, reject_null


class CategoryOut(BaseModel):
    code: str
    label: str
    group: str
    is_personnel: bool


class RevisionCreate(BaseModel):
    label: str
    effective_date: date
    note: str = ""


class RevisionOut(BaseModel):
    id: int
    project_id: int
    revision_number: int
    label: str
    status: str
    effective_date: date
    note: str
    created_by_username: str


class BudgetItemCreate(BaseModel):
    category: str
    item_number: int
    description: str
    justification: str = ""
    unit_value: Money
    planned_quantity: NonNegativeQuantity
    note: str = ""


class BudgetItemUpdate(BaseModel):
    description: str | None = None
    justification: str | None = None
    unit_value: Money | None = None
    planned_quantity: NonNegativeQuantity | None = None
    note: str | None = None

    _not_null = field_validator("description", "justification", "unit_value", "planned_quantity", "note")(reject_null)


class YieldUpdate(BaseModel):
    yield_amount: Decimal


class BudgetItemOut(BaseModel):
    id: int
    revision_id: int
    position_id: int
    category: str
    item_number: int
    description: str
    justification: str
    unit_value: Decimal
    planned_quantity: Decimal
    planned_value: Decimal
    yield_amount: Decimal
    note: str


class ItemBalanceOut(BaseModel):
    position_id: int
    category: str
    item_number: int
    description: str
    justification: str
    unit_value: Decimal
    planned_quantity: Decimal
    planned_value: Decimal
    yield_amount: Decimal
    committed: Decimal
    executed: Decimal
    balance: Decimal
    available_quantity: Decimal | None = None


class CategorySummaryOut(BaseModel):
    category: str
    label: str
    group: str
    planned_value: Decimal
    yield_amount: Decimal
    committed: Decimal
    executed: Decimal
    balance: Decimal
