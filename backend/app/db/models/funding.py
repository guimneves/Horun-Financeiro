"""Parcelas de repasse do projeto (a planilha as chama de "Parcelas": 1ª, 2ª,
3ª, 4ª, cada uma com valor e data). Servem para mostrar quanto de cada parcela
já foi utilizado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel, UniqueConstraint


class FundingInstallment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_installment_project_number"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    number: int  # 1, 2, 3...
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    expected_date: date | None = None
    note: str = ""
