"""Senha de coordenador — única, compartilhada por todo o módulo (não por
projeto). Quem sabe a senha ganha `role="coordenador"` transparente em
QUALQUER projeto que já consiga abrir (ver core/permissions.py,
`get_membership`) — sem precisar estar cadastrado como coordenador na
tabela de membros daquele projeto especificamente.

Só no esquema de desenvolvimento (decisão de 06/10/2026): no modo módulo o
papel vem do cargo no Horun e as rotas de senha respondem 409.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core import identity as identity_module
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import core_role, module_mode
from app.core.security import hash_password, issue_coordenador_token, verify_coordenador_token, verify_password
from app.db.models.module_settings import ModuleSettings
from app.db.session import get_session
from app.schemas.auth import CoordenadorLoginRequest, CoordenadorLoginResponse, CoordenadorPasswordChangeRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def whoami(identity: HorunIdentity = Depends(get_identity)) -> dict:
    """Quem é a pessoa, para a tela decidir o que mostrar (ex. "Novo
    projeto" só para o admin do Core, que é quem pode criar — a rota
    continua conferindo por conta própria)."""
    roles_from_core = module_mode()
    return {
        "user_id": identity.user_id,
        "username": identity.username,
        "role": identity.role,
        "is_core_admin": identity.role == "admin",
        "level": identity.level,
        "dev_mode": identity_module.DEV_MODE,
        # true = papéis pelo cargo no Horun (sem senha mestra); a tela então
        # usa `module_role` (o mesmo papel em todos os projetos).
        "roles_from_core": roles_from_core,
        "module_role": core_role(identity) if roles_from_core else None,
    }


def _reject_in_module_mode() -> None:
    if module_mode():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Neste servidor o papel vem do seu cargo no Horun — não há senha de coordenador "
            "(ela só existe no modo de desenvolvimento).",
        )


def _get_module_settings(session: Session) -> ModuleSettings:
    settings_row = session.get(ModuleSettings, 1)
    if settings_row is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Senha de coordenador não configurada neste servidor (defina MODULE_COORDENADOR_PASSWORD).",
        )
    return settings_row


# Senha única e compartilhada = alvo de tentativa e erro. Depois de
# MAX_FAILED_ATTEMPTS erros seguidos, a mesma pessoa (identidade do Core)
# fica LOCKOUT_SECONDS sem poder tentar. Em memória, por processo: basta
# para o backend de um worker só; zera ao reiniciar.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
_failed_attempts: dict[str, list[float]] = {}


def _check_lockout(user_id: str) -> None:
    now = time.monotonic()
    recent = [t for t in _failed_attempts.get(user_id, []) if now - t < LOCKOUT_SECONDS]
    _failed_attempts[user_id] = recent
    if len(recent) >= MAX_FAILED_ATTEMPTS:
        minutes = int((LOCKOUT_SECONDS - (now - recent[0])) // 60) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas erradas. Tente de novo em {minutes} min.",
        )


@router.post("/coordenador-session", response_model=CoordenadorLoginResponse)
def login_as_coordenador(
    body: CoordenadorLoginRequest,
    session: Session = Depends(get_session),
    identity: HorunIdentity = Depends(get_identity),
):
    _reject_in_module_mode()
    _check_lockout(identity.user_id)
    settings_row = _get_module_settings(session)
    if not verify_password(body.password, settings_row.coordenador_password_hash):
        _failed_attempts.setdefault(identity.user_id, []).append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha incorreta.")
    _failed_attempts.pop(identity.user_id, None)
    token, expires_at = issue_coordenador_token()
    return CoordenadorLoginResponse(token=token, expires_at=expires_at)


@router.post("/coordenador-password", status_code=status.HTTP_204_NO_CONTENT)
def change_coordenador_password(
    body: CoordenadorPasswordChangeRequest,
    x_horun_coordenador_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    _reject_in_module_mode()
    if not verify_coordenador_token(x_horun_coordenador_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão de coordenador inválida ou expirada.")
    settings_row = _get_module_settings(session)
    if not verify_password(body.current_password, settings_row.coordenador_password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha atual incorreta.")
    if len(body.new_password) < 6:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A nova senha precisa ter ao menos 6 caracteres.")
    settings_row.coordenador_password_hash = hash_password(body.new_password)
    session.add(settings_row)
    session.commit()
