"""Engine/sessão do banco — SQLite em desenvolvimento, PostgreSQL em
produção (troca via MODULE_DATABASE_URL, não de código — mesmo padrão do
Horun Core, ver Horun Core/backend/app/db/session.py).

`create_all()` só cria tabelas que ainda não existem — nunca altera uma
tabela que já existe, mesmo que o modelo Python ganhe uma coluna nova.
`_run_migrations()` cobre isso pra colunas adicionadas depois do primeiro
deploy (inofensivo em SQLite dev, essencial em Postgres produção).
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Importar os módulos de modelo garante que todas as tabelas estejam
# registradas no metadata antes do create_all — inclusive as com FK cruzada
# entre si (Project.active_revision_id <-> BudgetRevision.project_id).
from app.db.models import project as _project_models  # noqa: F401
from app.db.models import budget as _budget_models  # noqa: F401
from app.db.models import purchase as _purchase_models  # noqa: F401
from app.db.models import personnel as _personnel_models  # noqa: F401
from app.db.models import document as _document_models  # noqa: F401
from app.db.models import audit as _audit_models  # noqa: F401
from app.db.models import funding as _funding_models  # noqa: F401
from app.db.models import agent as _agent_models  # noqa: F401
from app.agent_server.models import MIGRATIONS as AGENT_MIGRATIONS

logger = logging.getLogger(__name__)

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


def _ensure_unique_index(name: str, table: str, columns: str) -> None:
    # Se já houver dados duplicados num banco antigo, o índice não pode ser
    # criado — avisa em vez de impedir o módulo de subir.
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON "{table}" ({columns})')
    except SQLAlchemyError:
        logger.warning("Não foi possível criar o índice único %s (dados duplicados?).", name)


def _run_migrations() -> None:
    # Ao adicionar um campo num modelo que já tem tabela em produção, somar
    # aqui uma chamada de _ensure_column (mesmo padrão do Core), no mesmo
    # commit que muda o modelo.
    _ensure_column("project", "drive_folder", "VARCHAR")
    _ensure_column("project", "balance_policy", "VARCHAR DEFAULT 'bloquear'")
    _ensure_column("document", "storage_kind", "VARCHAR DEFAULT 'upload'")
    _ensure_column("document", "sha256", "VARCHAR")
    _ensure_column("purchaseprocess", "origin", "VARCHAR DEFAULT 'manual'")
    _ensure_column("purchaseprocess", "drive_rel_path", "VARCHAR")
    _ensure_unique_index("uq_process_project_number", "purchaseprocess", "project_id, process_number")
    # colunas novas das tabelas do agente (pacote único — ver app/agent_server)
    for table, column, ddl_type in AGENT_MIGRATIONS:
        _ensure_column(table, column, ddl_type)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
