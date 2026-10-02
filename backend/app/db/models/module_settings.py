"""Configuração de módulo, uma linha só (id fixo = 1) — hoje só guarda o
hash da senha de coordenador, única e compartilhada por todo o módulo (não
por projeto)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModuleSettings(SQLModel, table=True):
    id: int | None = Field(default=1, primary_key=True)
    coordenador_password_hash: str
    updated_at: datetime = Field(default_factory=_utcnow)
