"""Processo de compra — uma linha por TENTATIVA de compra contra um item de
orçamento (não por revisão). Uma tentativa cancelada/rejeitada nunca é
reaberta — uma nova tentativa é um `PurchaseProcess` novo, com
`previous_attempt_id` apontando pra anterior (espelha as pastas reais
"<processo> - CANCELADO" ao lado da tentativa que deu certo).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Ordem = ordem natural do fluxo — usada pra ordenar colunas do quadro de
# compras no frontend. rejeitado/cancelado são terminais, alcançáveis de
# qualquer estado não-terminal (ver services/transitions.py).
PURCHASE_STATES = [
    "verificacao_orcamento",
    "cotacao",
    "aguardando_autorizacao",
    "autorizado",
    "nota_fiscal_emitida",
    "comprovante_recebimento",
    "concluido",
    "rejeitado",
    "cancelado",
]
TERMINAL_STATES = {"concluido", "rejeitado", "cancelado"}
IN_PROGRESS_STATES = set(PURCHASE_STATES) - TERMINAL_STATES


class PurchaseProcess(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    budget_position_id: int = Field(foreign_key="budgetposition.id", index=True)
    process_number: str | None = None  # Nº de processo COPPETEC — preenchido quando emitido
    title: str
    vendor: str | None = None  # Favorecido — pode ficar em branco até as cotações chegarem
    quantity: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    estimated_unit_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    estimated_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))  # conta como "comprometido"
    final_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2)))  # conta como "realizado"
    asset_registration_flag: bool = False  # "INCLUIR NA PLANILHA DE PATRIM."
    status: str = "verificacao_orcamento"
    previous_attempt_id: int | None = Field(default=None, foreign_key="purchaseprocess.id")
    cancel_reason: str | None = None
    created_by_user_id: str
    created_by_username: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    closed_at: datetime | None = None  # setado em rejeitado/cancelado também
