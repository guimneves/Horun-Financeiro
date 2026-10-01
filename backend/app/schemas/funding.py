from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InstallmentIn(BaseModel):
    amount: Decimal = Field(ge=0)
    expected_date: date | None = None
    note: str = ""


class InstallmentsReplace(BaseModel):
    """Substitui a lista inteira — o número da parcela é a posição (1ª, 2ª...)."""

    installments: list[InstallmentIn]


class InstallmentOut(BaseModel):
    number: int
    amount: Decimal
    expected_date: date | None
    note: str
    cumulative_amount: Decimal  # soma desta parcela e das anteriores
    # Fração (0 a 1) do acumulado já realizada; nulo enquanto a parcela
    # anterior não foi toda utilizada (o "-" da planilha).
    utilization: Decimal | None


class GroupTotalOut(BaseModel):
    group: str
    label: str
    planned_value: Decimal
    yield_amount: Decimal
    committed: Decimal
    executed: Decimal
    balance: Decimal


class OverviewOut(BaseModel):
    """Equivalente ao "Quadro Resumo" da planilha."""

    groups: list[GroupTotalOut]
    total: GroupTotalOut
    total_executed: Decimal
    installments: list[InstallmentOut]
    items_over_budget: int  # itens com saldo negativo — a planilha só mostrava um "verificar"


class AuditEventOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int | None
    action: str
    detail: str
    username: str
    created_at: datetime
