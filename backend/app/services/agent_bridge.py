"""Ponte entre o backend e o Horun Agent (PC onde o OneDrive está sincronizado).

Do ponto de vista de quem chama (uma rota), continua síncrono: cria uma
`AgentTask` e espera — consultando o banco em intervalos curtos — até o agente
reportar o resultado (`POST /agent/tasks/{id}/result`) ou estourar o prazo.
Mesmo desenho do `agent_bridge.py` do RE7S, com três diferenças:

- falha RÁPIDA se nenhum agente foi visto recentemente (em vez de esperar o
  prazo inteiro por algo que não vai acontecer);
- tarefa que estourou o prazo é marcada `expired` e nunca mais oferecida ao
  agente (no RE7S ela continua pendente e seria executada tarde demais);
- arquivos vêm em pedaços (`offset`/`length`), com limite de tamanho.

Sessões de banco curtas e independentes a cada consulta: nunca reter a sessão
do pedido HTTP durante a espera (mesmo bug que o RE7S já encontrou com SQLite).
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.db import session as db_session
from app.db.models.agent import AgentDevice, AgentTask

# Um agente consulta o servidor a cada poucos segundos; sem sinal por mais que
# isso, considera-se desligado ou sem rede.
AGENT_ONLINE_WINDOW = timedelta(seconds=120)


class AgentTaskError(RuntimeError):
    """O agente respondeu, mas com falha. `code` segue docs/AGENT_CONTRACT.md."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code

    @property
    def not_found(self) -> bool:
        # Agente antigo não manda `code`: reconhece pelo texto, como o RE7S.
        return self.code == "not_found" or "não encontrado" in str(self)


class AgentTimeoutError(AgentTaskError):
    """O agente não respondeu dentro do prazo."""


class AgentOfflineError(AgentTaskError):
    """Nenhum agente foi visto recentemente."""


@dataclass
class TreeEntry:
    path: str
    is_dir: bool
    size: int | None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def parse_version(text: str | None) -> tuple[int, ...]:
    """"0.2" -> (0, 2). Sem versão (agente antigo) ou ilegível -> (0,)."""
    try:
        return tuple(int(part) for part in (text or "").strip().split("."))
    except ValueError:
        return (0,)


# A partir desta versão o agente entende `list_tree`, `offset`/`length` e o
# campo opcional `code`, e tolera campos extras na tarefa. O agente anterior
# monta a tarefa com `Task(**t)` — um campo desconhecido derruba o laço dele —,
# então o servidor só envia os campos novos a quem declarar esta versão.
EXTENDED_PROTOCOL = (0, 2)


@dataclass
class AgentState:
    online: bool
    extended: bool  # algum agente online já fala o protocolo estendido


def agent_state() -> AgentState:
    now = datetime.now(timezone.utc)
    online = extended = False
    with Session(db_session.engine) as s:
        for device in s.exec(select(AgentDevice).where(AgentDevice.revoked_at.is_(None))):  # type: ignore[union-attr]
            if device.last_seen_at is None or now - _as_utc(device.last_seen_at) > AGENT_ONLINE_WINDOW:
                continue
            online = True
            if parse_version(device.agent_version) >= EXTENDED_PROTOCOL:
                extended = True
    return AgentState(online=online, extended=extended)


def agent_online() -> bool:
    return agent_state().online


def _enqueue(*, needs_extended: bool = False, **fields) -> int:
    state = agent_state()
    if not state.online:
        raise AgentOfflineError(
            "O agente do drive está offline (nenhum sinal recente). Confira se o PC com o OneDrive está ligado, "
            "com rede e com o Horun Agent rodando."
        )
    if needs_extended and not state.extended:
        raise AgentTaskError(
            "O Horun Agent instalado é antigo e não sabe listar pastas. Atualize-o para a versão 0.2 ou superior "
            "(ver docs/AGENT_CONTRACT.md).",
            "agent_outdated",
        )
    with Session(db_session.engine) as s:
        task = AgentTask(status="pending", **fields)
        s.add(task)
        s.commit()
        return task.id


def _expire(task_id: int) -> None:
    with Session(db_session.engine) as s:
        task = s.get(AgentTask, task_id)
        if task is not None and task.status == "pending":
            task.status = "expired"
            task.completed_at = datetime.now(timezone.utc)
            s.add(task)
            s.commit()


def _wait(task_id: int, timeout: float | None, poll_interval: float = 0.2) -> AgentTask:
    timeout = settings.agent_task_timeout_seconds if timeout is None else timeout
    deadline = time.monotonic() + timeout
    while True:
        with Session(db_session.engine) as s:
            task = s.get(AgentTask, task_id)
            if task is None:
                raise AgentTaskError(f"tarefa {task_id} sumiu do banco")
            if task.status in ("done", "error"):
                s.expunge(task)
                return task
        if time.monotonic() >= deadline:
            _expire(task_id)
            raise AgentTimeoutError(
                f"O agente não respondeu em {timeout:g}s — confira se o PC com o OneDrive está ligado e com rede."
            )
        time.sleep(poll_interval)


def _run(timeout: float | None, *, needs_extended: bool = False, **fields) -> AgentTask:
    task = _wait(_enqueue(needs_extended=needs_extended, **fields), timeout)
    if not task.result_ok:
        raise AgentTaskError(task.result_error or "falha no agente", task.result_error_code)
    return task


def list_tree(root: str, path: str, *, recursive: bool, timeout: float | None = None) -> list[TreeEntry]:
    task = _run(timeout, needs_extended=True, op="list_tree", root=root, path=path, recursive=recursive)
    if task.result_truncated:
        raise AgentTaskError(
            "A pasta tem arquivos demais para listar de uma vez (limite do agente). Use uma pasta de projeto menor."
        )
    return [TreeEntry(e["path"], bool(e["is_dir"]), e.get("size")) for e in json.loads(task.result_entries or "[]")]


def read_bytes(root: str, path: str, *, max_bytes: int | None = None, timeout: float | None = None) -> bytes:
    """Lê o arquivo inteiro em pedaços. `max_bytes` (padrão: o limite do módulo)
    recusa arquivos maiores logo no primeiro pedaço, sem baixar o resto."""
    limit = settings.agent_max_file_bytes if max_bytes is None else max_bytes
    chunk = settings.agent_chunk_bytes
    parts: list[bytes] = []
    offset = 0
    while True:
        task = _run(timeout, op="read_file", root=root, path=path, offset=offset, length=chunk)
        data = base64.b64decode(task.result_content_base64 or "")
        total = task.result_size
        if total is None:
            # Agente antigo: devolveu o arquivo inteiro de uma vez (não recebeu offset/length).
            if len(data) > limit:
                raise AgentTaskError(
                    f"Arquivo de {len(data) / 1024 / 1024:.1f} MB acima do limite de {limit / 1024 / 1024:.0f} MB.",
                    "too_large",
                )
            return data
        if total > limit:
            raise AgentTaskError(
                f"Arquivo de {total / 1024 / 1024:.1f} MB acima do limite de {limit / 1024 / 1024:.0f} MB.", "too_large"
            )
        parts.append(data)
        offset += len(data)
        if offset >= total or not data:
            return b"".join(parts)
