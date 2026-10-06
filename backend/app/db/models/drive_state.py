"""Estado da sincronização com o drive nos dois sentidos (decisão de
06/10/2026 — ver services/drive_write.py e services/drive_auto_sync.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DriveAutoSyncState(SQLModel, table=True):
    """Uma linha só (id=1): tudo o que decide "se a sincronização automática
    roda agora" fica no banco — vários workers ou um reinício não fazem
    rodar duas vezes (mesmo padrão do RE7S, app/modules/auto_sync.py)."""

    id: int | None = Field(default=None, primary_key=True)
    last_run_at: datetime | None = None  # última rodada que chegou ao fim
    lease_until: datetime | None = None  # concessão (UPDATE condicional) ou prazo de nova tentativa
    last_status: str = ""  # ok | parcial | pulada | erro
    last_message: str = ""
    # JSON {project_id: {"arquivos": n, "processos": n, "copias": n, "erro": "..."}}
    last_detail: str = ""


class DriveUnlinkedPath(SQLModel, table=True):
    """Arquivo do drive que alguém DESVINCULOU no módulo (ou cópia de um
    anexo removido). O arquivo continua no drive — o módulo nunca apaga —,
    mas a sincronização (inclusive a automática) não o vincula de novo."""

    __table_args__ = (UniqueConstraint("project_id", "rel_path", name="uq_unlinked_project_path"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    rel_path: str  # relativo à pasta do projeto
    unlinked_by_username: str = ""
    unlinked_at: datetime = Field(default_factory=_utcnow)
