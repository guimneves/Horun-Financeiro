"""Processo de compra — uma linha por TENTATIVA de compra contra um item de
orçamento (não por revisão). Uma tentativa cancelada/rejeitada nunca é
reaberta — uma nova tentativa é um `PurchaseProcess` novo, com
`previous_attempt_id` apontando pra anterior (espelha as pastas reais
"<processo> - CANCELADO" ao lado da tentativa que deu certo).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Index, Numeric
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Ordem = ordem natural do fluxo — usada pra ordenar colunas do quadro de
# compras no frontend. rejeitado/cancelado são terminais, alcançáveis de
# qualquer estado não-terminal (ver services/transitions.py).
PURCHASE_STATES = [
    "verificacao_orcamento",
    "cotacao",
    "aguardando_autorizacao",
    "autorizado",
    "nota_fiscal_emitida",
    "comprovante_recebimento",
    "concluido",
    "rejeitado",
    "cancelado",
]
TERMINAL_STATES = {"concluido", "rejeitado", "cancelado"}
IN_PROGRESS_STATES = set(PURCHASE_STATES) - TERMINAL_STATES
# Saldo, no mesmo critério da planilha de acompanhamento: o valor passa a ser
# "realizado" quando o processo é autorizado (a planilha lança uma linha
# assim que existe nº de processo COPPETEC). Antes disso é só "comprometido"
# — extensão do programa, a planilha não tem essa coluna.
PRE_AUTHORIZATION_COMMITTED_STATES = {"verificacao_orcamento", "cotacao", "aguardando_autorizacao"}
REALIZED_STATES = {"autorizado", "nota_fiscal_emitida", "comprovante_recebimento", "concluido"}
# Antes da autorização, quem está tocando a compra (não necessariamente o
# coordenador) ainda pode editar os campos básicos do processo — depois de
# autorizado, só o coordenador mexe (ver update_process em routes_purchases.py).
PRE_AUTHORIZATION_STATES = {"verificacao_orcamento", "cotacao", "aguardando_autorizacao"}


class PurchaseProcess(SQLModel, table=True):
    # Nº de processo COPPETEC único por projeto (vários processos sem número
    # ainda — nulos não colidem). O número é guardado normalizado ("AAAA-N"),
    # ver app/core/process_number.py.
    __table_args__ = (Index("uq_process_project_number", "project_id", "process_number", unique=True),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    budget_position_id: int = Field(foreign_key="budgetposition.id", index=True)
    process_number: str | None = None  # Nº de processo COPPETEC — preenchido quando emitido
    title: str
    vendor: str | None = None  # Favorecido — pode ficar em branco até as cotações chegarem
    quantity: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    estimated_unit_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))
    estimated_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))  # conta como "comprometido"
    final_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2)))  # conta como "realizado"
    asset_registration_flag: bool = False  # "INCLUIR NA PLANILHA DE PATRIM."
    status: str = "verificacao_orcamento"
    previous_attempt_id: int | None = Field(default=None, foreign_key="purchaseprocess.id")
    cancel_reason: str | None = None
    origin: str = "manual"  # manual | drive_import (criado a partir da pasta do drive)
    drive_rel_path: str | None = None  # pasta deste processo no drive, relativa à pasta do projeto
    # A pasta "SEM NUMERO ..." precisa passar a ter o nº (que acabou de ser
    # informado), mas o drive não respondeu — a sincronização automática
    # tenta de novo (services/drive_write.py `rename_process_folder`).
    drive_rename_pending: bool = False
    created_by_user_id: str
    created_by_username: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    # Quando o valor passou a contar como realizado (autorização) — gravada ao
    # autorizar pelo módulo, ou informada à mão. Nula nos importados do drive:
    # o gráfico de ritmo estima pelo nº de processo (services/pace.py).
    realized_on: date | None = None
    # Lançamento da planilha SEM nº de processo (DOA, ressarcimento, passagem
    # pela agência...): identidade da linha, para a sincronização não duplicar
    # (services/ledger.py `UnnumberedEntry.ref`).
    ledger_ref: str | None = Field(default=None, index=True)
    closed_at: datetime | None = None  # setado em rejeitado/cancelado também
    # Nota fiscal registrada ACIMA do saldo do item, confirmada por alguém
    # depois do aviso (routes_purchases.transition_process). Nunca bloqueia —
    # a nota é um fato —, mas fica marcada para aparecer na lista.
    over_balance_confirmed_by: str | None = None
    over_balance_confirmed_at: datetime | None = None
