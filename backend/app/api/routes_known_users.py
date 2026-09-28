"""Diretório de usuários já vistos pelo módulo — ver
db/models/known_user.py e core/known_users_middleware.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.identity import get_identity
from app.db.models.known_user import KnownUser
from app.db.session import get_session
from app.schemas.known_user import KnownUserOut

router = APIRouter(prefix="/known-users", tags=["known-users"])


@router.get("", response_model=list[KnownUserOut])
def list_known_users(
    session: Session = Depends(get_session),
    _identity=Depends(get_identity),
):
    return session.exec(select(KnownUser).order_by(KnownUser.username)).all()
