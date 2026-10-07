from __future__ import annotations

from datetime import date, datetime
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
    coppetec_process_number: str | None = None


class BudgetItemUpdate(BaseModel):
    description: str | None = None
    justification: str | None = None
    unit_value: Money | None = None
    planned_quantity: NonNegativeQuantity | None = None
    note: str | None = None
    coppetec_process_number: str | None = None

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
    # None pra quem não é coordenador — ver core/redaction.py. Colaborador
    # só sabe se há saldo (has_balance no ItemBalanceOut), não os valores.
    unit_value: Decimal | None
    planned_quantity: Decimal
    planned_value: Decimal | None
    yield_amount: Decimal | None
    note: str
    coppetec_process_number: str | None


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
    coppetec_process_number: str | None
    available_quantity: Decimal | None = None


class PurchaseCategoryOut(BaseModel):
    """Tipo de despesa e se está liberado para compras novas neste projeto."""

    category: str
    label: str
    group: str
    is_personnel: bool
    open: bool  # Equipe Executora: sempre false (não usa o fluxo de compra)
    item_count: int  # itens da revisão ativa nesta categoria
    updated_by: str | None = None
    updated_at: datetime | None = None


class PurchaseCategoryUpdate(BaseModel):
    """Liberar (true) ou fechar (false) para compras novas."""

    open: bool


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


class BudgetImportItemOut(BaseModel):
    category: str
    item_number: int
    description: str
    justification: str
    unit_value: Decimal
    planned_quantity: Decimal
    planned_value: Decimal
    yield_amount: Decimal
    sheet_row: int


class BudgetImportCategoryOut(BaseModel):
    category: str
    label: str
    count: int
    planned_total: Decimal
    yield_total: Decimal


class BudgetImportPreviewOut(BaseModel):
    """O que a importação da aba "Saldo por Item" criaria — nada gravado."""

    categories: list[BudgetImportCategoryOut]
    items: list[BudgetImportItemOut]
    skipped_sections: list[str]
    warnings: list[str]


class BudgetImportResultOut(BaseModel):
    revision: RevisionOut
    items_created: int
    warnings: list[str]
