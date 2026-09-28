from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


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
    unit_value: Decimal
    planned_quantity: Decimal
    note: str = ""


class BudgetItemUpdate(BaseModel):
    description: str | None = None
    justification: str | None = None
    unit_value: Decimal | None = None
    planned_quantity: Decimal | None = None
    note: str | None = None


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
    # None pra quem não é coordenador — ver core/redaction.py. Colaborador
    # só sabe se há saldo (has_balance no ItemBalanceOut), não os valores.
    unit_value: Decimal | None
    planned_quantity: Decimal
    planned_value: Decimal | None
    yield_amount: Decimal | None
    note: str


class ItemBalanceOut(BaseModel):
    position_id: int
    category: str
    item_number: int
    description: str
    justification: str
    unit_value: Decimal | None
    planned_quantity: Decimal
    planned_value: Decimal | None
    yield_amount: Decimal | None
    committed: Decimal | None
    executed: Decimal | None
    balance: Decimal | None
    has_balance: bool


class CategorySummaryOut(BaseModel):
    category: str
    label: str
    group: str
    planned_value: Decimal | None
    yield_amount: Decimal | None
    committed: Decimal | None
    executed: Decimal | None
    balance: Decimal | None
    has_balance: bool
