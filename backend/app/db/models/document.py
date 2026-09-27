"""Anexo tipado — ligado a um PurchaseProcess ou a um PersonnelAssignment
(nunca os dois). Arquivo em disco (`app/core/files.py`), só caminho +
metadados aqui — volume esperado (várias cotações + NF + comprovantes por
vários anos de projeto) grande demais pra caber bem em BLOB de banco.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DOC_TYPES = [
    "cotacao",
    "solicitacao_autorizacao",
    "nota_fiscal",
    "comprovante_recebimento",
    "recibo_pessoal",
    "outro",
]
MAX_QUOTES_PER_PROCESS = 3


class Document(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    purchase_process_id: int | None = Field(default=None, foreign_key="purchaseprocess.id", index=True)
    personnel_assignment_id: int | None = Field(default=None, foreign_key="personnelassignment.id", index=True)
    doc_type: str
    original_filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    period_label: str | None = None  # ex. "2024-03" — usado por recibo_pessoal (Milestone 3)
    note: str | None = None
    uploaded_by_user_id: str
    uploaded_by_username: str
    uploaded_at: datetime = Field(default_factory=_utcnow)
