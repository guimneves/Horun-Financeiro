"""Identidade do usuário autenticado.

Em produção, o módulo roda atrás do Horun Core e nunca fica exposto direto
à rede do laboratório (só alcançável através do gateway do Core — mesma
disciplina já aplicada ao Postgres/backend do RE7S: sem porta pro host).
O Core valida o login e repassa a identidade via cabeçalhos internos
confiáveis (X-Horun-User-Id/X-Horun-User/X-Horun-Role).

Em desenvolvimento standalone (HORUN_DEV_MODE=true), esses cabeçalhos não
existem — usa-se um usuário fixo, para permitir desenvolver e testar o
módulo inteiro sem o Core rodando (Prompt_Horun_Core.md, seção 3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

DEV_MODE = os.environ.get("HORUN_DEV_MODE", "false").lower() == "true"


@dataclass
class HorunIdentity:
    user_id: str
    username: str
    role: str


def get_identity(
    x_horun_user_id: str | None = Header(default=None),
    x_horun_user: str | None = Header(default=None),
    x_horun_role: str | None = Header(default=None),
) -> HorunIdentity:
    if DEV_MODE:
        return HorunIdentity(user_id="dev", username="dev", role="admin")

    if not x_horun_user_id or not x_horun_user or not x_horun_role:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Identidade não informada — este módulo só deve ser acessado através do Horun Core.",
        )
    return HorunIdentity(user_id=x_horun_user_id, username=x_horun_user, role=x_horun_role)
