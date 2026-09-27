"""Autorização DENTRO do módulo — separada da identidade que o Core injeta
(app.core.identity só diz quem é a pessoa, não o que ela pode fazer aqui).

Papéis do módulo (coordenador/colaborador) são geridos por
`ProjectMembership`, uma tabela deste módulo — o `role` do cabeçalho do
Core (`X-Horun-Role`) só é usado no único ponto em que este módulo precisa
saber se a pessoa é administradora máxima do Horun: autorizar a criação de
um projeto novo (ver Prompt_Horun_Core.md, seção 6 — o Core decide *se* a
pessoa entra no módulo; o módulo decide *o que* ela pode fazer aqui
dentro).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.identity import HorunIdentity, get_identity
from app.db.models.project import ProjectMembership
from app.db.session import get_session


def get_membership(
    project_id: int,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
) -> ProjectMembership:
    membership = session.exec(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == identity.user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem acesso a este projeto.")
    return membership


def require_coordenador(
    membership: ProjectMembership = Depends(get_membership),
) -> ProjectMembership:
    if membership.role != "coordenador":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação restrita ao coordenador do projeto.")
    return membership


def require_core_admin(identity: HorunIdentity = Depends(get_identity)) -> HorunIdentity:
    if identity.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o administrador máximo do Horun pode criar um projeto novo.",
        )
    return identity
