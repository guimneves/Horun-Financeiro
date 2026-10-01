"""Drive do Financeiro: ler as pastas do projeto (plano, sem gravar),
sincronizá-las com o banco e consultar/baixar os arquivos pelo programa.
Tudo aqui é leitura do drive — o módulo nunca escreve nem apaga nada nele.
"""

from __future__ import annotations

import mimetypes
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.config import settings
from app.core.drive import DriveError, fs_path, project_drive_dir, safe_join
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.schemas.drive import (
    DriveBrowseOut,
    DriveEntryOut,
    DriveScanRequest,
    DriveStatusOut,
    ProcessPlanOut,
    ScanReportOut,
    SyncResultOut,
)
from app.services.drive_scan import scan_project_folder
from app.services.drive_sync import SyncPlan, apply_sync, plan_sync
from app.services.ledger import LedgerError, LedgerResult, read_ledger

router = APIRouter(prefix="/projects/{project_id}/drive", tags=["drive"])


def _project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    return project


def _project_dir(project: Project) -> str:
    try:
        return str(project_drive_dir(project))
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _build_plan(session: Session, project: Project, body: DriveScanRequest) -> SyncPlan:
    project_dir = _project_dir(project)
    ledger: LedgerResult | None = None
    if body.ledger_path:
        if not body.ledger_path.lower().endswith(".xlsx"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A planilha de valores precisa ser um .xlsx.")
        try:
            ledger = read_ledger(str(safe_join(project_drive_dir(project), body.ledger_path)))
        except (DriveError, LedgerError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    try:
        scan = scan_project_folder(project_dir)
    except OSError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Não foi possível ler as pastas do drive: {exc}") from exc
    return plan_sync(session, project, scan, ledger)


def _report(plan: SyncPlan) -> ScanReportOut:
    return ScanReportOut(
        summary=plan.summary(),
        processes=[
            ProcessPlanOut(
                category=i.scanned.category,
                item_number=i.scanned.item_number,
                folder=i.scanned.folder,
                process_number=i.scanned.process_number,
                title=i.scanned.title,
                cancelled=i.scanned.cancelled,
                inferred_status=i.status or i.scanned.inferred_status,
                action=i.action,
                value=i.value,
                quantity=i.quantity,
                vendor=i.vendor,
                value_source=i.value_source,
                files_total=len(i.scanned.files),
                new_files=i.new_files,
                warnings=i.warnings,
            )
            for i in plan.items
        ],
        unrecognized=plan.scan.unrecognized,
        ignored_folders=plan.scan.ignored_folders,
        duplicate_numbers=plan.scan.duplicate_numbers,
        ledger_skipped=plan.ledger_skipped,
        ledger_unused=plan.ledger_unused,
    )


@router.get("/status", response_model=DriveStatusOut)
def drive_status(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    if not settings.drive_root:
        return DriveStatusOut(
            configured=False, project_folder=project.drive_folder, available=False,
            message="O drive não está configurado neste servidor (MODULE_DRIVE_ROOT).",
        )
    try:
        project_drive_dir(project)
    except DriveError as exc:
        return DriveStatusOut(
            configured=True, project_folder=project.drive_folder, available=False, message=str(exc)
        )
    return DriveStatusOut(configured=True, project_folder=project.drive_folder, available=True)


@router.post("/scan", response_model=ScanReportOut)
def scan_drive(
    project_id: int,
    body: DriveScanRequest,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Lê as pastas e devolve o que SERIA criado — não grava nada."""
    return _report(_build_plan(session, _project(session, project_id), body))


@router.post("/sync", response_model=SyncResultOut)
def sync_drive(
    project_id: int,
    body: DriveScanRequest,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Cria os processos que faltam e vincula os arquivos novos. Idempotente."""
    project = _project(session, project_id)
    plan = _build_plan(session, project, body)
    result = apply_sync(session, project, plan, identity)
    return SyncResultOut(**result, summary=plan.summary())


@router.get("/browse", response_model=DriveBrowseOut)
def browse_drive(
    project_id: int,
    path: str = "",
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    try:
        base = project_drive_dir(project)
        folder = safe_join(base, path)
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not os.path.isdir(fs_path(folder)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pasta não encontrada.")

    rel = path.replace("\\", "/").strip("/")
    entries: list[DriveEntryOut] = []
    with os.scandir(fs_path(folder)) as it:
        for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.casefold())):
            if entry.name.startswith("~$") or entry.name.startswith("."):
                continue
            entries.append(
                DriveEntryOut(
                    name=entry.name,
                    is_dir=entry.is_dir(),
                    rel_path=f"{rel}/{entry.name}" if rel else entry.name,
                    size_bytes=None if entry.is_dir() else entry.stat().st_size,
                )
            )
    parent = None if not rel else (rel.rsplit("/", 1)[0] if "/" in rel else "")
    return DriveBrowseOut(path=rel, parent=parent, entries=entries)


@router.get("/file")
def download_drive_file(
    project_id: int,
    path: str,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    try:
        target = fs_path(safe_join(project_drive_dir(project), path))
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not os.path.isfile(target):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado.")
    name = os.path.basename(path.replace("\\", "/"))
    return FileResponse(target, media_type=mimetypes.guess_type(name)[0] or "application/octet-stream", filename=name)
