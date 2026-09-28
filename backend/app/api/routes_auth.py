"""Senha de coordenador — única, compartilhada por todo o módulo (não por
projeto). Quem sabe a senha ganha `role="coordenador"` transparente em
QUALQUER projeto que já consiga abrir (ver core/permissions.py,
`get_membership`) — sem precisar estar cadastrado como coordenador na
tabela de membros daquele projeto especificamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.security import hash_password, issue_coordenador_token, verify_coordenador_token, verify_password
from app.db.models.module_settings import ModuleSettings
from app.db.session import get_session
from app.schemas.auth import CoordenadorLoginRequest, CoordenadorLoginResponse, CoordenadorPasswordChangeRequest

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_module_settings(session: Session) -> ModuleSettings:
    settings_row = session.get(ModuleSettings, 1)
    if settings_row is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Configuração do módulo não inicializada.")
    return settings_row


@router.post("/coordenador-session", response_model=CoordenadorLoginResponse)
def login_as_coordenador(body: CoordenadorLoginRequest, session: Session = Depends(get_session)):
    settings_row = _get_module_settings(session)
    if not verify_password(body.password, settings_row.coordenador_password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha incorreta.")
    token, expires_at = issue_coordenador_token()
    return CoordenadorLoginResponse(token=token, expires_at=expires_at)


@router.post("/coordenador-password", status_code=status.HTTP_204_NO_CONTENT)
def change_coordenador_password(
    body: CoordenadorPasswordChangeRequest,
    x_horun_coordenador_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
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
