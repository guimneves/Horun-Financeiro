"""Rotas /agent/* do Horun Agent — o programa instalado no PC onde o OneDrive
está sincronizado, que dá ao backend acesso de LEITURA ao drive sem abrir
porta nenhuma para dentro (ele é quem consulta o servidor). Vêm do pacote
único do servidor do agente (`app/agent_server/routes.py`, o mesmo do RE7S);
contrato no `PROTOCOL.md` do Agent-Horun e em `docs/AGENT_CONTRACT.md`.

Administração (código de enrolamento, listar/revogar): admin do Core, pelo
gateway. As rotas do próprio agente (`/agent/enroll`, `/agent/tasks`,
`/agent/tasks/{id}/result`) se autenticam pelo `device_token` e chegam por
uma porta estreita própria (ver docs/AGENT_CONTRACT.md, "Rede"), nunca pelo
gateway do Core.
"""

from __future__ import annotations

from app.agent_server.routes import build_router
from app.core.permissions import require_core_admin
from app.db.session import get_session


def _actor(identity) -> tuple[int | None, str | None]:
    # o id do Core chega como texto ("dev" no modo de desenvolvimento)
    return (int(identity.user_id) if str(identity.user_id).isdigit() else None, identity.username)


router = build_router(get_session=get_session, admin_dependency=require_core_admin, actor_of=_actor)
