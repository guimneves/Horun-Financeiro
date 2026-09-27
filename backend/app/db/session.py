"""Engine/sessão do banco — SQLite em desenvolvimento, PostgreSQL em
produção (troca via MODULE_DATABASE_URL, não de código — mesmo padrão do
Horun Core, ver Horun Core/backend/app/db/session.py).

`create_all()` só cria tabelas que ainda não existem — nunca altera uma
tabela que já existe, mesmo que o modelo Python ganhe uma coluna nova.
`_run_migrations()` cobre isso pra colunas adicionadas depois do primeiro
deploy (inofensivo em SQLite dev, essencial em Postgres produção).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Importar os módulos de modelo garante que todas as tabelas estejam
# registradas no metadata antes do create_all — inclusive as com FK cruzada
# entre si (Project.active_revision_id <-> BudgetRevision.project_id).
from app.db.models import project as _project_models  # noqa: F401
from app.db.models import budget as _budget_models  # noqa: F401
from app.db.models import purchase as _purchase_models  # noqa: F401
from app.db.models import document as _document_models  # noqa: F401

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    from sqlalchemy import inspect

    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    if column in existing:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl_type}')


def _run_migrations() -> None:
    # Nenhuma coluna pós-lançamento ainda — primeira versão do módulo.
    # Ao adicionar um campo num modelo que já tem tabela em produção, somar
    # aqui uma chamada de _ensure_column (mesmo padrão do Core), no mesmo
    # commit que muda o modelo.
    pass


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
