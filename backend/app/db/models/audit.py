"""Histórico de eventos — quem fez o quê e quando. Uma linha por ação
relevante (criar/editar/transição de processo, documento enviado/removido,
sincronização com o drive...), nunca editada nem apagada. É o que responde,
na prestação de contas, "quem autorizou isto e quando".
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    entity_type: str = Field(index=True)  # purchase_process | document | drive | installments ...
    entity_id: int | None = Field(default=None, index=True)
    action: str
    detail: str = ""  # JSON em texto: estados de/para, motivo, campos alterados...
    user_id: str
    username: str
    created_at: datetime = Field(default_factory=_utcnow, index=True)
