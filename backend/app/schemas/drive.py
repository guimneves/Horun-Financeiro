from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DriveScanRequest(BaseModel):
    # Planilha de acompanhamento com os valores, RELATIVA à pasta do projeto
    # (ex. "0_Saldo por item/NOVA 25465 Acompanhamento de saldo_reformulação.xlsx").
    # Sem ela, os processos entram com valor zero.
    ledger_path: str | None = None


class ProcessPlanOut(BaseModel):
    category: str
    item_number: int
    folder: str
    process_number: str
    title: str
    cancelled: bool
    inferred_status: str
    action: str  # criar | existe | sem_item_no_orcamento | duplicado_na_pasta
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


class SyncResultOut(BaseModel):
    processos_criados: int
    arquivos_vinculados: int
    summary: dict[str, int]  # o plano que foi aplicado


class DriveStatusOut(BaseModel):
    configured: bool  # MODULE_DRIVE_ROOT definido neste servidor
    project_folder: str | None
    available: bool  # a pasta do projeto existe e está acessível agora
    message: str | None = None


class DriveEntryOut(BaseModel):
    name: str
    is_dir: bool
    rel_path: str
    size_bytes: int | None


class DriveBrowseOut(BaseModel):
    path: str
    parent: str | None
    entries: list[DriveEntryOut]
