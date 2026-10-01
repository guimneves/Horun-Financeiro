"""Tabelas do Horun Agent (o programa instalado no PC onde o OneDrive está
sincronizado) — mesmo desenho do RE7S (`Rock Eval Horun Dev/backend/app/db/
models.py`), com os campos extras do contrato do Financeiro
(`docs/AGENT_CONTRACT.md`). Só são usadas com `MODULE_DRIVE_MODE=agent`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentEnrollCode(SQLModel, table=True):
    """Código de uso único que um admin gera para instalar um agente novo."""

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    created_by_user_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    used_at: datetime | None = None
    used_by_device_id: int | None = Field(default=None, foreign_key="agentdevice.id")


class AgentDevice(SQLModel, table=True):
    """Uma instalação do agente já enrolada. Só o hash do token é guardado."""

    id: int | None = Field(default=None, primary_key=True)
    device_name: str
    token_hash: str = Field(index=True, unique=True)
    agent_version: str | None = None
    enrolled_at: datetime = Field(default_factory=_utcnow)
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class AgentTask(SQLModel, table=True):
    """Uma tarefa de arquivo pedida ao agente. Criada só internamente pela ponte
    (`services/agent_bridge.py`), nunca por uma rota pública.

    status: pending (esperando o agente) | done | error | expired (o backend
    desistiu de esperar — não deve mais ser oferecida ao agente)."""

    id: int | None = Field(default=None, primary_key=True)
    op: str  # read_file | list_tree | list_files | write_file
    root: str
    path: str | None = None
    glob: str | None = None
    content_base64: str | None = None  # entrada, só write_file
    offset: int | None = None  # read_file
    length: int | None = None  # read_file
    recursive: bool | None = None  # list_tree
    status: str = Field(default="pending", index=True)
    result_ok: bool | None = None
    result_content_base64: str | None = None
    result_size: int | None = None  # tamanho total do arquivo (read_file)
    result_entries: str | None = None  # JSON de list_tree: [{path, is_dir, size}]
    result_truncated: bool | None = None
    result_paths: str | None = None  # JSON de list_files
    result_error: str | None = None
    result_error_code: str | None = None
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    completed_at: datetime | None = None
