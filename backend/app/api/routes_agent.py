"""Rotas do Horun Agent — o programa instalado no PC onde o OneDrive está
sincronizado, que dá ao backend acesso aos arquivos do drive sem abrir porta
nenhuma para dentro (ele é quem consulta o servidor). Contrato em
`docs/AGENT_CONTRACT.md` e no `PROTOCOL.md` do repositório do agente.

Administração (código de enrolamento, listar/revogar) exige o admin do Core.
As rotas do próprio agente (`/agent/enroll`, `/agent/tasks`, `/agent/tasks/
{id}/result`) se autenticam pelo `device_token`, NÃO por sessão de usuário —
por isso o gateway do Core precisa deixar `/m/financeiro/agent/*` passar.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.identity import HorunIdentity
from app.core.permissions import require_core_admin
from app.db.models.agent import AgentDevice, AgentEnrollCode, AgentTask
from app.db.session import get_session
from app.services.agent_bridge import EXTENDED_PROTOCOL, parse_version

router = APIRouter(prefix="/agent", tags=["agent"])


def _hash_token(token: str) -> str:
    # Token de alta entropia gerado por nós (não uma senha escolhida): sha256
    # basta — só não pode vazar em claro se o banco vazar.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_device(
    authorization: str | None = Header(default=None),
    x_horun_agent_version: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> AgentDevice:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token do agente ausente.")
    device = session.exec(
        select(AgentDevice).where(AgentDevice.token_hash == _hash_token(authorization[7:].strip()))
    ).first()
    if device is None or device.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token do agente inválido ou revogado.")
    device.last_seen_at = datetime.now(timezone.utc)
    if x_horun_agent_version:
        device.agent_version = x_horun_agent_version.strip()[:32]
    session.add(device)
    session.commit()
    return device


# ---------------------------------------------------------------- schemas


class EnrollCodeOut(BaseModel):
    code: str


class DeviceOut(BaseModel):
    id: int
    device_name: str
    agent_version: str | None
    enrolled_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None


class EnrollIn(BaseModel):
    enroll_code: str
    device_name: str


class EnrollOut(BaseModel):
    device_token: str


class TaskResultIn(BaseModel):
    ok: bool
    content_base64: str | None = None
    size: int | None = None
    paths: list[str] | None = None
    entries: list[dict] | None = None
    truncated: bool | None = None
    error: str | None = None
    code: str | None = None


# ---------------------------------------------------- administração (admin)


@router.post("/enroll-codes", response_model=EnrollCodeOut)
def create_enroll_code(
    admin: HorunIdentity = Depends(require_core_admin), session: Session = Depends(get_session)
):
    """Código de uso único para instalar um agente novo (vai no `config.json`
    do agente, `enroll_code`, na primeira vez que ele roda)."""
    code = secrets.token_hex(4).upper()
    session.add(AgentEnrollCode(code=code, created_by_user_id=admin.user_id))
    session.commit()
    return EnrollCodeOut(code=code)


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(
    _admin: HorunIdentity = Depends(require_core_admin), session: Session = Depends(get_session)
):
    """Diagnóstico: quem enrolou, qual versão e quando foi visto pela última vez."""
    return list(session.exec(select(AgentDevice).order_by(AgentDevice.enrolled_at.desc())))  # type: ignore[attr-defined]


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: int,
    _admin: HorunIdentity = Depends(require_core_admin),
    session: Session = Depends(get_session),
):
    device = session.get(AgentDevice, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instalação não encontrada.")
    device.revoked_at = datetime.now(timezone.utc)
    session.add(device)
    session.commit()
    return {"ok": True}


# --------------------------------------------------------- agente: enrolar


@router.post("/enroll", response_model=EnrollOut)
def enroll(payload: EnrollIn, session: Session = Depends(get_session)):
    entry = session.exec(select(AgentEnrollCode).where(AgentEnrollCode.code == payload.enroll_code)).first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Código de enrolamento não encontrado.")
    if entry.used_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Código de enrolamento já foi usado.")

    token = secrets.token_urlsafe(32)
    device = AgentDevice(device_name=payload.device_name, token_hash=_hash_token(token))
    session.add(device)
    session.commit()
    session.refresh(device)

    entry.used_at = datetime.now(timezone.utc)
    entry.used_by_device_id = device.id
    session.add(entry)
    session.commit()
    return EnrollOut(device_token=token)


# ---------------------------------------------------- agente: fila de tarefas

_LEGACY_OPS = {"read_file", "write_file", "list_files"}


def _task_payload(task: AgentTask, extended: bool) -> dict:
    payload = {
        "id": task.id,
        "op": task.op,
        "root": task.root,
        "path": task.path,
        "content_base64": task.content_base64,
        "glob": task.glob,
    }
    if extended:
        payload.update(offset=task.offset, length=task.length, recursive=task.recursive)
    return payload


@router.get("/tasks")
def get_pending_tasks(device: AgentDevice = Depends(get_device), session: Session = Depends(get_session)):
    """Tarefas pendentes. Agente que não declara versão ≥ 0.2 recebe só os seis
    campos de sempre e nunca uma operação nova — o `Task(**t)` estrito dele
    quebraria com um campo desconhecido (ver docs/AGENT_CONTRACT.md §6)."""
    extended = parse_version(device.agent_version) >= EXTENDED_PROTOCOL
    tasks = session.exec(
        select(AgentTask).where(AgentTask.status == "pending").order_by(AgentTask.created_at)  # type: ignore[arg-type]
    ).all()
    return {"tasks": [_task_payload(t, extended) for t in tasks if extended or t.op in _LEGACY_OPS]}


@router.post("/tasks/{task_id}/result")
def report_task_result(
    task_id: int,
    payload: TaskResultIn,
    _device: AgentDevice = Depends(get_device),
    session: Session = Depends(get_session),
):
    task = session.get(AgentTask, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarefa não encontrada.")
    if task.status != "pending":
        # Já resolvida (ou expirada por prazo do backend): idempotente, sem reprocessar.
        return {"ok": True}

    task.result_ok = payload.ok
    task.result_content_base64 = payload.content_base64
    task.result_size = payload.size
    task.result_entries = json.dumps(payload.entries) if payload.entries is not None else None
    task.result_truncated = payload.truncated
    task.result_paths = json.dumps(payload.paths) if payload.paths is not None else None
    task.result_error = payload.error
    task.result_error_code = payload.code
    task.status = "done" if payload.ok else "error"
    task.completed_at = datetime.now(timezone.utc)
    session.add(task)
    session.commit()
    return {"ok": True}
