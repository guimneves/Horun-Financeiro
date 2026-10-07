"""Identidade do usuário autenticado.

Em produção, o módulo roda atrás do Horun Core e nunca fica exposto direto
à rede do laboratório (só alcançável através do gateway do Core — mesma
disciplina já aplicada ao Postgres/backend do RE7S: sem porta pro host).
O Core valida o login e repassa a identidade via cabeçalhos internos
confiáveis (X-Horun-User-Id/X-Horun-User/X-Horun-Role e, desde 01/10/2026,
X-Horun-Level/X-Horun-Level-Name — o cargo da pessoa no Horun).

Em desenvolvimento standalone (HORUN_DEV_MODE=true), esses cabeçalhos não
existem de verdade — usa-se um usuário fixo, para permitir desenvolver e
testar o módulo inteiro sem o Core rodando (Prompt_Horun_Core.md, seção 3).
Mesmo assim, se o frontend mandar esses cabeçalhos por conta própria (o
seletor "Ver como", dev-only), eles são respeitados — só pra permitir
alternar entre papéis (coordenador/colaborador) localmente sem precisar do
Core. Nunca acontece em produção, onde DEV_MODE é sempre false.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

DEV_MODE = os.environ.get("HORUN_DEV_MODE", "false").lower() == "true"

# Níveis (cargos) do Horun Core — Prompt_Horun_Modulo.md, seção 5.
LEVEL_ADMIN = 1  # administrador máximo
LEVEL_COORDENADOR = 2  # coordenador(a)
LEVEL_IC = 5  # iniciação científica (ou sem posição) — o menor nível


def parse_level(raw: str | None, role: str) -> int:
    """Nível do Core a partir de X-Horun-Level. Sem o cabeçalho (Core antigo)
    ou com valor inválido: quem tem X-Horun-Role "admin" conta como
    coordenador(a) (nível 2 — o Core manda "admin" para os níveis 1 e 2);
    qualquer outro, como o menor nível (5)."""
    try:
        level = int(str(raw).strip())
    except (TypeError, ValueError):
        level = 0
    if 1 <= level <= 5:
        return level
    return LEVEL_COORDENADOR if role == "admin" else LEVEL_IC


@dataclass
class HorunIdentity:
    user_id: str
    username: str
    role: str
    # Cargo no Horun: 1 admin máximo, 2 coordenador(a), 3 pesquisador,
    # 4 técnico, 5 IC. Decide o papel no módulo (core/permissions.py).
    level: int = LEVEL_IC


def get_identity(
    x_horun_user_id: str | None = Header(default=None),
    x_horun_user: str | None = Header(default=None),
    x_horun_role: str | None = Header(default=None),
    x_horun_level: str | None = Header(default=None),
) -> HorunIdentity:
    if DEV_MODE:
        if x_horun_user_id and x_horun_user:
            role = x_horun_role or "admin"
            return HorunIdentity(
                user_id=x_horun_user_id, username=x_horun_user, role=role, level=parse_level(x_horun_level, role)
            )
        return HorunIdentity(user_id="dev", username="dev", role="admin", level=LEVEL_ADMIN)

    if not x_horun_user_id or not x_horun_user or not x_horun_role:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Identidade não informada — este módulo só deve ser acessado através do Horun Core.",
        )
    return HorunIdentity(
        user_id=x_horun_user_id,
        username=x_horun_user,
        role=x_horun_role,
        level=parse_level(x_horun_level, x_horun_role),
    )
