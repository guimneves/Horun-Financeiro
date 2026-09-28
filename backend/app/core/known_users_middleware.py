"""Registra automaticamente quem já apareceu numa requisição (cabeçalhos
X-Horun-User-Id/X-Horun-User, injetados pelo Core em produção) — ver
db/models/known_user.py pro porquê. Não usa `get_identity`/`Depends` de
propósito: middleware roda pra TODA rota, inclusive as que ainda vão
adicionar seu próprio `Depends(get_identity)` depois; ler o cabeçalho cru
aqui evita duplicar a lógica de DEV_MODE só pra este efeito colateral."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.models.known_user import KnownUser
from app.db.session import engine


class KnownUsersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.headers.get("x-horun-user-id")
        username = request.headers.get("x-horun-user")
        if user_id and username:
            from datetime import datetime, timezone

            from sqlmodel import Session

            with Session(engine) as session:
                existing = session.get(KnownUser, user_id)
                if existing is None:
                    existing = KnownUser(user_id=user_id, username=username)
                existing.username = username
                existing.last_seen_at = datetime.now(timezone.utc)
                session.add(existing)
                session.commit()
        return await call_next(request)
