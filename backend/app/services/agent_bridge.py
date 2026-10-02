"""Ponte entre o backend e o Horun Agent (PC onde o OneDrive está
sincronizado) — usada só com `MODULE_DRIVE_MODE=agent`.

A implementação é o pacote único do servidor do agente, o MESMO do RE7S
(cópia em `app/agent_server/`, gerada por `Agent-Horun/scripts/
vendor_server.py` — não edite lá). Aqui fica só o que é do Financeiro: a
interface que `core/drive_backend.py` usa (sem sessão: o drive é lido fora
de qualquer pedido ao banco), falha rápida com agente offline, o tamanho
dos pedaços e o limite de arquivo, lidos de `core/config.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.agent_server import bridge as impl
from app.agent_server.bridge import (  # noqa: F401 — reexportados
    AgentOfflineError,
    AgentTaskError,
    AgentTimeoutError,
    AgentTooOldError,
    file_not_found,
)
from app.agent_server.settings import settings as agent_settings
from app.core.config import settings
from app.db import session as db_session

# Sem agente conectado, avisa na hora em vez de esperar o prazo inteiro.
agent_settings.fail_fast_when_offline = True
agent_settings.timeout_provider = lambda: settings.agent_task_timeout_seconds


@dataclass
class TreeEntry:
    path: str
    is_dir: bool
    size: int | None


@dataclass
class AgentState:
    online: bool
    extended: bool  # algum agente online sabe listar pastas (list_tree, >= 0.4.0)


def agent_state() -> AgentState:
    online = impl._online_devices(db_session.engine)
    return AgentState(
        online=bool(online),
        extended=any(impl.supports(d.agent_version, "list_tree") for d in online),
    )


def agent_online() -> bool:
    return agent_state().online


def list_tree(root: str, path: str, *, recursive: bool, timeout: float | None = None) -> list[TreeEntry]:
    with Session(db_session.engine) as s:
        entries = impl.list_tree(s, root, path, recursive=recursive, timeout=timeout)
    return [TreeEntry(e["path"], bool(e["is_dir"]), e.get("size")) for e in entries]


def read_bytes(root: str, path: str, *, max_bytes: int | None = None, timeout: float | None = None) -> bytes:
    """Arquivo inteiro — em pedaços se o agente suportar (>= 0.3.0), senão
    de uma vez. `max_bytes` (padrão: o limite do módulo) recusa arquivo
    maior já no primeiro pedaço (`code="too_large"`)."""
    limit = settings.agent_max_file_bytes if max_bytes is None else max_bytes
    with Session(db_session.engine) as s:
        chunk = settings.agent_chunk_bytes if impl.agent_supports(s, "read_range") else None
        return impl.read_bytes(s, root, path, timeout=timeout, chunk_size=chunk, max_bytes=limit)
