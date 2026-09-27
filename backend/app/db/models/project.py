"""Projeto e associação de usuário a projeto.

Um `Project` é um projeto financiado (ex. Petrobras/COPPETEC), totalmente
independente dos demais — orçamento, itens, compras e pessoal nunca cruzam
de um projeto pro outro. `ProjectMembership` dá o papel do usuário DENTRO
deste módulo (coordenador/colaborador) — não tem relação com o papel que o
Horun Core injeta no cabeçalho (esse só diz se a pessoa é admin máximo do
Core, usado apenas para autorizar a criação de um projeto novo, ver
core/permissions.py). `user_id` vem do cabeçalho X-Horun-User-Id como
string solta, sem FK — o módulo nunca acessa o banco do Core.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)  # nº do processo COPPETEC, ex. "25.465"
    name: str
    funding_agency: str = "Petrobras"
    foundation: str = "COPPETEC/UFRJ"
    status: str = "ativo"  # ativo | suspenso | encerrado
    start_date: date | None = None
    end_date: date | None = None
    # Aponta pra revisão orçamentária vigente — evita varrer BudgetRevision
    # procurando status="ativa" toda vez. De propósito SEM foreign_key: uma
    # FK real criaria um ciclo com BudgetRevision.project_id (que aponta de
    # volta pra Project), o que impede o SQLAlchemy de ordenar DROP/CREATE
    # TABLE sem truques extras (use_alter) que o SQLite não suporta bem.
    # Validado na camada de API, não no banco — mesma filosofia já usada
    # pras listas fechadas em string (ver EXPENSE_CATEGORIES).
    active_revision_id: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class ProjectMembership(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_membership_project_user"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    user_id: str = Field(index=True)
    username: str
    role: str  # coordenador | colaborador
    granted_by_user_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
