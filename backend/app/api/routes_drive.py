"""Drive do Financeiro: ler as pastas do projeto (plano, sem gravar),
sincronizá-las com o banco e consultar/baixar os arquivos pelo programa.
Tudo aqui é leitura do drive. A escrita (cópia dos anexos, pasta "SEM
NUMERO" que ganha o nº) fica em services/drive_write.py; a sincronização
automática, em services/drive_auto_sync.py.

O drive pode estar no disco deste servidor ou num PC distante, alcançado
pelo Horun Agent (`MODULE_DRIVE_MODE`) — estas rotas não sabem qual:
falam com `get_drive_backend()` (core/drive_backend.py), sempre com
caminhos relativos à raiz do drive.
"""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session

from app.core.config import settings
from app.core.drive import DriveError, DriveNotFound, join_rel, project_folder
from app.core.drive_backend import AGENT_OFFLINE_MESSAGE, DriveEntry, get_drive_backend, serve_file
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.schemas.drive import (
    AutoSyncOut,
    DriveBrowseOut,
    DriveEntryOut,
    DriveScanRequest,
    DriveStatusOut,
    ProcessPlanOut,
    ScanReportOut,
    SyncResultOut,
)
from app.services.af_number import fill_numbers_task
from app.services.drive_scan import fold, scan_entries
from app.services.drive_write import drive_write_enabled
from app.services.drive_sync import SyncPlan, apply_sync, plan_sync, sync_lock
from app.services.ledger import LedgerError, LedgerResult, read_ledger

router = APIRouter(prefix="/projects/{project_id}/drive", tags=["drive"])


def _project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    return project


def _folder(project: Project) -> str:
    try:
        return project_folder(project.drive_folder)
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _relative_to(folder: str, entries: list[DriveEntry]) -> list[DriveEntry]:
    """Entradas do drive (relativas à raiz) -> relativas à pasta do projeto."""
    prefix = folder + "/"
    return [
        DriveEntry(e.path[len(prefix):], e.is_dir, e.size) for e in entries if e.path.startswith(prefix)
    ]


def _pick_ledger(names: list[str]) -> str | None:
    """Entre as .xlsx da pasta, a de acompanhamento: na pasta real convivem
    "NOVA ... Acompanhamento de saldo...", "antiga.xlsx", "antiga 2.xlsx" e
    "Calculo Pessoal.xlsx". Só escolhe quando não há dúvida."""
    if len(names) <= 1:
        return names[0] if names else None
    candidates = [n for n in names if "acompanhamento" in fold(n)] or names
    current = [n for n in candidates if not any(w in fold(n) for w in ("antig", "backup", "copia", "old"))]
    return current[0] if len(current) == 1 else None


def _find_ledger(entries: list[DriveEntry]) -> str | None:
    """A planilha de acompanhamento da pasta "0_Saldo por item" (ver
    `_pick_ledger`) — evita sincronizar sem valores por esquecer o campo
    (visto na prática: 420 processos entraram com R$ 0). `entries` relativas
    à pasta do projeto."""
    by_folder: dict[str, list[str]] = {}
    for e in entries:
        parts = e.path.split("/")
        if e.is_dir or len(parts) != 2 or "saldo por item" not in fold(parts[0]):
            continue
        if parts[1].lower().endswith(".xlsx") and not parts[1].startswith("~$"):
            by_folder.setdefault(parts[0], []).append(parts[1])
    for folder, sheets in sorted(by_folder.items()):
        chosen = _pick_ledger(sorted(sheets))
        if chosen:
            return f"{folder}/{chosen}"
    return None


class PlanError(Exception):
    """Não deu para montar o plano. `status_code`: 409 (drive) | 422 (planilha)."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def build_sync_plan(session: Session, project: Project, ledger_path: str | None) -> SyncPlan:
    """Lê as pastas (e a planilha) e calcula o plano — usado pelo botão e
    pela sincronização automática. `PlanError` se o drive ou a planilha falhar."""
    try:
        folder = project_folder(project.drive_folder)
    except DriveError as exc:
        raise PlanError(str(exc), status.HTTP_409_CONFLICT) from exc
    backend = get_drive_backend()
    try:
        entries = _relative_to(folder, backend.list_tree(folder))
    except DriveError as exc:
        raise PlanError(str(exc), status.HTTP_409_CONFLICT) from exc
    except OSError as exc:
        raise PlanError(f"Não foi possível ler as pastas do drive: {exc}", status.HTTP_409_CONFLICT) from exc
    ledger: LedgerResult | None = None
    ledger_path = (ledger_path or "").strip() or _find_ledger(entries)
    if ledger_path:
        if not ledger_path.lower().endswith(".xlsx"):
            raise PlanError("A planilha de valores precisa ser um .xlsx.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        try:
            ledger = read_ledger(backend.read_bytes(join_rel(folder, ledger_path)))
        except DriveNotFound as exc:
            raise PlanError(f"Planilha não encontrada: {ledger_path}", status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
        except (DriveError, LedgerError) as exc:
            raise PlanError(str(exc), status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    plan = plan_sync(session, project, scan_entries(entries), ledger)
    plan.ledger_path = ledger_path if ledger else None
    return plan


def _build_plan(session: Session, project: Project, body: DriveScanRequest) -> SyncPlan:
    try:
        return build_sync_plan(session, project, body.ledger_path)
    except PlanError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


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
        ledger_path=plan.ledger_path,
    )


def _auto_sync_info(session: Session, project_id: int) -> AutoSyncOut:
    from app.services import drive_auto_sync

    return AutoSyncOut(**drive_auto_sync.project_info(session, project_id))


@router.get("/status", response_model=DriveStatusOut)
def drive_status(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    result = _drive_status(project)
    result.write_enabled = drive_write_enabled()
    result.auto_sync = _auto_sync_info(session, project_id)
    return result


def _drive_status(project: Project) -> DriveStatusOut:
    mode = settings.drive_mode
    if mode == "agent":
        # Sem ida ao PC aqui (a tela consulta o estado com frequência): só
        # se algum agente foi visto agora há pouco, e se ele sabe listar pastas.
        from app.services.agent_bridge import agent_state

        state = agent_state()
        message = None
        if not state.online:
            message = AGENT_OFFLINE_MESSAGE
        elif not state.extended:
            message = "O Horun Agent instalado é antigo para ler pastas — atualize para a versão 0.4.0 ou mais nova."
        return DriveStatusOut(
            configured=True, mode=mode, project_folder=project.drive_folder,
            available=state.online and state.extended and bool(project.drive_folder),
            message=message or (None if project.drive_folder else "Este projeto ainda não tem pasta do drive configurada."),
        )
    if not settings.drive_root:
        return DriveStatusOut(
            configured=False, mode=mode, project_folder=project.drive_folder, available=False,
            message="O drive não está configurado neste servidor (MODULE_DRIVE_ROOT).",
        )
    try:
        get_drive_backend().list_tree(project_folder(project.drive_folder), recursive=False)
    except DriveNotFound:
        return DriveStatusOut(
            configured=True, mode=mode, project_folder=project.drive_folder, available=False,
            message=f"A pasta do projeto não existe no drive: {project.drive_folder}",
        )
    except DriveError as exc:
        return DriveStatusOut(
            configured=True, mode=mode, project_folder=project.drive_folder, available=False, message=str(exc)
        )
    return DriveStatusOut(configured=True, mode=mode, project_folder=project.drive_folder, available=True)


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
    background: BackgroundTasks,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Cria os processos que faltam e vincula os arquivos novos. Idempotente."""
    project = _project(session, project_id)
    # espera a sincronização automática, se estiver rodando agora
    with sync_lock:
        plan = _build_plan(session, project, body)
        result = apply_sync(session, project, plan, identity)
    # nº das autorizações de fornecimento vinculadas a processos sem nº — em
    # segundo plano (pelo agente, cada PDF espera o PC responder)
    background.add_task(fill_numbers_task, project.id)
    return SyncResultOut(**result, summary=plan.summary())


@router.get("/browse", response_model=DriveBrowseOut)
def browse_drive(
    project_id: int,
    path: str = "",
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    folder = _folder(project)
    try:
        rel = join_rel("", path)
        listed = get_drive_backend().list_tree(join_rel(folder, rel), recursive=False)
    except DriveNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pasta não encontrada.") from exc
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    entries: list[DriveEntryOut] = []
    for entry in sorted(_relative_to(folder, listed), key=lambda e: (not e.is_dir, e.path.rsplit("/", 1)[-1].casefold())):
        name = entry.path.rsplit("/", 1)[-1]
        if name.startswith("~$") or name.startswith("."):
            continue
        entries.append(DriveEntryOut(name=name, is_dir=entry.is_dir, rel_path=entry.path, size_bytes=entry.size))
    parent = None if not rel else (rel.rsplit("/", 1)[0] if "/" in rel else "")
    return DriveBrowseOut(path=rel, parent=parent, entries=entries)


@router.get("/file")
def download_drive_file(
    project_id: int,
    path: str,
    inline: bool = False,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    project = _project(session, project_id)
    folder = _folder(project)
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    try:
        # inline: exibir na página (PDF, imagem, texto) em vez de baixar
        return serve_file(join_rel(folder, path), name, mimetypes.guess_type(name)[0] or "application/octet-stream", inline=inline)
    except DriveNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado.") from exc
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
