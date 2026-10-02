"""Diretório próprio do módulo — este módulo não tem acesso à lista de
usuários do Horun Core (cada módulo é isolado, só recebe a identidade de
quem faz a requisição, nunca uma lista de todo mundo cadastrado). Em vez
disso, registramos automaticamente todo usuário que já apareceu numa
requisição (via cabeçalho injetado pelo Core — ver
core/known_users_middleware.py), pra o coordenador escolher de uma lista
em vez de digitar o ID de cor na hora de dar acesso a um projeto."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnownUser(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    username: str
    last_seen_at: datetime = Field(default_factory=_utcnow)
