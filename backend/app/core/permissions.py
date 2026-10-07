"""Autorização DENTRO do módulo — separada da identidade que o Core injeta
(app.core.identity só diz quem é a pessoa, não o que ela pode fazer aqui).

Dois esquemas (decisão de 06/10/2026):

* **Modo módulo** (atrás do Horun Core, `module_mode()` verdadeiro): o papel
  vem do CARGO no Horun (`X-Horun-Level`). Níveis 1 (administrador máximo) e
  2 (coordenador/a) são coordenador em TODOS os projetos; qualquer outra
  pessoa que chegou ao módulo (o Core já conferiu o acesso ao módulo) é
  colaborador em todos. Não precisa de linha em `ProjectMembership` e a
  senha mestra é ignorada. `ProjectMembership` continua existindo só como
  "participantes do projeto" — quem recebe os avisos (services/notifications.py).

* **Desenvolvimento** (HORUN_DEV_MODE=true, `Apresentar_Financeiro.bat`):
  o esquema antigo — papel pela tabela `ProjectMembership` deste módulo,
  elevação a coordenador pela senha mestra (routes_auth.py). É o que o
  seletor "Ver como" usa para trocar de visão rapidamente.

Para portar a outros módulos (Reagentes, Amostras): basta `module_mode()`,
`core_role()` e o primeiro bloco de `get_membership`.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.core import identity as identity_module
from app.core.identity import LEVEL_COORDENADOR, HorunIdentity, get_identity
from app.core.security import verify_coordenador_token
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session


def module_mode() -> bool:
    """Papéis pelo cargo no Horun? Sempre que NÃO é desenvolvimento. Lido do
    módulo a cada chamada, para os testes poderem ligar o DEV_MODE."""
    return not identity_module.DEV_MODE


def core_role(identity: HorunIdentity) -> str:
    """Papel no módulo pelo cargo no Horun: níveis 1–2 coordenam, o resto colabora."""
    return "coordenador" if identity.level <= LEVEL_COORDENADOR else "colaborador"


def get_membership(
    project_id: int,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    x_horun_coordenador_token: str | None = Header(default=None),
) -> ProjectMembership:
    if module_mode():
        if session.get(Project, project_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
        # Objeto solto (sem id), NUNCA gravado no banco: só carrega o papel
        # efetivo para as rotas (redação de valores, require_coordenador).
        return ProjectMembership(
            project_id=project_id,
            user_id=identity.user_id,
            username=identity.username,
            role=core_role(identity),
        )

    membership = session.exec(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == identity.user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem acesso a este projeto.")
    if membership.role != "coordenador" and verify_coordenador_token(x_horun_coordenador_token):
        # Sessão elevada pela senha mestra do módulo (ver routes_auth.py) —
        # atua como coordenador aqui sem alterar o cadastro real de
        # membros; é um objeto solto, nunca commitado no banco.
        membership = membership.model_copy(update={"role": "coordenador"})
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
