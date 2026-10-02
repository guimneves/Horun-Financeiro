from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core.money import Money, PositiveQuantity, reject_null


class PurchaseProcessCreate(BaseModel):
    budget_position_id: int
    title: str
    quantity: PositiveQuantity
    estimated_unit_value: Money
    vendor: str | None = None
    previous_attempt_id: int | None = None
    asset_registration_flag: bool = False


class PurchaseProcessUpdate(BaseModel):
    title: str | None = None
    vendor: str | None = None
    quantity: PositiveQuantity | None = None
    estimated_unit_value: Money | None = None
    process_number: str | None = None
    asset_registration_flag: bool | None = None

    # vendor/process_number podem ser limpos com null; estes, não.
    _not_null = field_validator("title", "quantity", "estimated_unit_value", "asset_registration_flag")(reject_null)


class PurchaseProcessOut(BaseModel):
    id: int
    project_id: int
    budget_position_id: int
    process_number: str | None
    title: str
    vendor: str | None
    quantity: Decimal
    # None pra quem não é coordenador — ver core/redaction.py.
    estimated_unit_value: Decimal | None
    estimated_value: Decimal | None
    final_value: Decimal | None
    asset_registration_flag: bool
    status: str
    previous_attempt_id: int | None
    cancel_reason: str | None
    origin: str = "manual"
    drive_rel_path: str | None = None
    created_by_username: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    closed_at: datetime | None
    # Nota fiscal acima do saldo, confirmada depois do aviso (sinal na lista).
    over_balance_confirmed_by: str | None = None
    over_balance_confirmed_at: datetime | None = None
    # Avisos que não impedem a operação (ex.: valor acima do saldo num projeto
    # com política "avisar"). Só vem preenchido na resposta de criar/editar.
    warnings: list[str] = []


class AvailabilityCheckRequest(BaseModel):
    budget_position_id: int
    quantity: PositiveQuantity
    estimated_unit_value: Money


class AvailabilityCheckOut(BaseModel):
    available: bool


class TransitionRequest(BaseModel):
    action: str
    reason: str | None = None
    vendor: str | None = None
    process_number: str | None = None
    final_value: Money | None = None
    # Só coordenador: avança mesmo sem o documento exigido, justificando.
    override_reason: str | None = None
    # Nota fiscal acima do saldo do item: a primeira tentativa volta 428 com o
    # aviso; reenviar com true registra mesmo assim (e marca o processo).
    confirm_over_balance: bool = False


class DocumentTypeUpdate(BaseModel):
    doc_type: str


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    original_filename: str
    storage_kind: str = "upload"
    content_type: str
    size_bytes: int
    period_label: str | None
    note: str | None
    uploaded_by_username: str
    uploaded_at: datetime
