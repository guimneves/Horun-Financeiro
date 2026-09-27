"""Equipe Executora — estrutura própria, não é uma "compra": acumula
automaticamente enquanto a atribuição estiver `ativo`, em vez de passar por
cotação/autorização/nota fiscal. `Person` é escopada por projeto (mesma
pessoa em dois projetos gera dois registros — cada projeto é totalmente
independente).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    full_name: str
    cpf: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class PersonnelAssignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    budget_position_id: int = Field(foreign_key="budgetposition.id", index=True)
    role_title: str
    monthly_rate: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    start_date: date
    end_date: date | None = None  # nulo enquanto `ativo`
    status: str = "ativo"  # ativo | encerrado
    created_by_user_id: str
    created_at: datetime = Field(default_factory=_utcnow)
