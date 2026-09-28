from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


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
    monthly_rate: Decimal
    start_date: date


class AssignmentUpdate(BaseModel):
    role_title: str | None = None
    monthly_rate: Decimal | None = None
    start_date: date | None = None


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
