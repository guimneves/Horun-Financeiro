from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DriveScanRequest(BaseModel):
    # Planilha de acompanhamento com os valores, RELATIVA à pasta do projeto
    # (ex. "0_Saldo por item/NOVA 25465 Acompanhamento de saldo_reformulação.xlsx").
    # Vazia: usa a única .xlsx da pasta "... Saldo por item" do projeto, se houver.
    # Sem planilha, os processos entram com valor zero.
    ledger_path: str | None = None


class ProcessPlanOut(BaseModel):
    category: str
    item_number: int
    folder: str
    process_number: str
    title: str
    cancelled: bool
    inferred_status: str
    # criar | criar_da_planilha | criar_sem_numero | existe | preencher_valor | corrigir_item |
    # sem_item_no_orcamento | duplicado_na_pasta
    action: str
    value: Decimal
    quantity: Decimal
    vendor: str | None
    value_source: str  # planilha | pendente | cancelado
    files_total: int
    new_files: int
    warnings: list[str]


class ScanReportOut(BaseModel):
    summary: dict[str, int]
    processes: list[ProcessPlanOut]
    unrecognized: list[dict[str, str]]
    ignored_folders: list[dict[str, str]]
    duplicate_numbers: list[str]
    ledger_skipped: list[str]
    ledger_unused: list[str]
    ledger_path: str | None = None  # planilha usada (informada ou achada em "0_Saldo por item")


class SyncResultOut(BaseModel):
    processos_criados: int
    valores_preenchidos: int = 0  # processos que estavam com R$ 0 e receberam o valor da planilha
    itens_corrigidos: int = 0  # processos que passaram do item da pasta para o da planilha
    arquivos_vinculados: int
    summary: dict[str, int]  # o plano que foi aplicado


class AutoSyncOut(BaseModel):
    """Sincronização automática com o drive (services/drive_auto_sync.py)."""

    enabled: bool
    interval_minutes: int
    last_run_at: datetime | None = None  # última rodada que chegou ao fim
    last_status: str = ""  # ok | parcial | pulada | erro
    last_message: str = ""
    # deste projeto, na última rodada
    new_files: int = 0
    new_processes: int = 0
    copies: int = 0
    error: str | None = None


class DriveStatusOut(BaseModel):
    configured: bool  # MODULE_DRIVE_ROOT definido neste servidor (ou modo agente)
    mode: str = "local"  # "local" (disco deste servidor) | "agent" (Horun Agent)
    project_folder: str | None
    available: bool  # a pasta do projeto existe e está acessível agora
    message: str | None = None
    # MODULE_DRIVE_WRITE: anexos são copiados para a pasta do processo
    write_enabled: bool = False
    auto_sync: AutoSyncOut | None = None


class DriveEntryOut(BaseModel):
    name: str
    is_dir: bool
    rel_path: str
    size_bytes: int | None


class DriveBrowseOut(BaseModel):
    path: str
    parent: str | None
    entries: list[DriveEntryOut]
