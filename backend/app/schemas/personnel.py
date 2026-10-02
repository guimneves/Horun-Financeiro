from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core.money import Money, reject_null


class PersonCreate(BaseModel):
    full_name: str
    cpf: str | None = None


class PersonOut(BaseModel):
    id: int
    project_id: int
    full_name: str
    cpf: str | None


class AssignmentCreate(BaseModel):
    person_id: int
    budget_position_id: int
    role_title: str
    monthly_rate: Money
    start_date: date


class AssignmentUpdate(BaseModel):
    role_title: str | None = None
    monthly_rate: Money | None = None
    start_date: date | None = None

    _not_null = field_validator("role_title", "monthly_rate", "start_date")(reject_null)


class AssignmentOut(BaseModel):
    id: int
    project_id: int
    person_id: int
    person_name: str
    budget_position_id: int
    role_title: str
    # None pra quem não é coordenador — ver core/redaction.py.
    monthly_rate: Decimal | None
    start_date: date
    end_date: date | None
    status: str
    accrued_months: Decimal
    accrued_value: Decimal | None
    committed_future_value: Decimal | None


class CloseAssignmentRequest(BaseModel):
    end_date: date


class PersonnelImportRowOut(BaseModel):
    item_number: int
    role_title: str
    person_name: str
    status: str
    start_date: date
    end_date: date | None
    monthly_rate: Decimal
    sheet_value: Decimal | None  # realizado segundo a planilha
    accrued_value: Decimal  # realizado calculado pelo módulo, até hoje
    sheet_row: int
    position_found: bool  # a vaga existe no orçamento do projeto
    already_imported: bool  # mesma pessoa, vaga e início já cadastrados


class PersonnelImportPreviewOut(BaseModel):
    rows: list[PersonnelImportRowOut]
    warnings: list[str]
    sheet_total: Decimal
    accrued_total: Decimal


class PersonnelImportResultOut(BaseModel):
    people_created: int
    assignments_created: int
    skipped: int
    warnings: list[str]
