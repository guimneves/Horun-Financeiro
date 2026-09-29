from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PurchaseProcessCreate(BaseModel):
    budget_position_id: int
    title: str
    quantity: Decimal
    estimated_unit_value: Decimal
    vendor: str | None = None
    previous_attempt_id: int | None = None
    asset_registration_flag: bool = False


class PurchaseProcessUpdate(BaseModel):
    title: str | None = None
    vendor: str | None = None
    quantity: Decimal | None = None
    estimated_unit_value: Decimal | None = None
    process_number: str | None = None
    asset_registration_flag: bool | None = None


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
    created_by_username: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    closed_at: datetime | None


class AvailabilityCheckRequest(BaseModel):
    budget_position_id: int
    quantity: Decimal
    estimated_unit_value: Decimal


class AvailabilityCheckOut(BaseModel):
    available: bool


class TransitionRequest(BaseModel):
    action: str
    reason: str | None = None
    vendor: str | None = None
    process_number: str | None = None
    final_value: Decimal | None = None


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    original_filename: str
    content_type: str
    size_bytes: int
    period_label: str | None
    note: str | None
    uploaded_by_username: str
    uploaded_at: datetime
