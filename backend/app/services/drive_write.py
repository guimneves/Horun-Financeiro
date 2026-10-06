"""Escrita no drive — o sentido "módulo → pasta" da sincronização (decisão
do mantenedor, 06/10/2026; antes o módulo só lia).

Só com `MODULE_DRIVE_WRITE=true` (no modo agente, a pasta também precisa
estar "read-write" no config.json do Horun Agent). Regras:

- só cria arquivos NOVOS: nome ocupado vira "nome (2).pdf", "(3)"...;
  NUNCA sobrescreve e NUNCA apaga arquivo do drive;
- o anexo enviado ao módulo continua guardado no servidor (cópia de
  segurança); a cópia no drive é feita depois da resposta, em segundo plano,
  e o que não deu certo (agente offline, pasta só leitura) é tentado de novo
  pela sincronização automática (services/drive_auto_sync.py);
- a única movimentação é a da pasta "SEM NUMERO <data> <título>" de um
  processo, quando ele ganha o nº COPPETEC: os arquivos dela passam para
  "<AAAA-N> <título>", na mesma pasta de item. A pasta vazia que sobra só é
  apagada no modo local (o agente não apaga pastas).

Pasta do processo, relativa à pasta do projeto:
`<pasta da categoria>/<Item N - descrição>/<AAAA-N título | SEM NUMERO dd-mm-aaaa título>`
— reaproveitando as pastas de categoria e de item que já existirem.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import drive_configured, settings
from app.core.drive import (
    DriveError,
    DriveFileExists,
    DriveNotFound,
    DriveUnavailable,
    join_rel,
    project_folder,
)
from app.core.drive_backend import DriveBackend, DriveEntry, get_drive_backend
from app.core.files import resolve_path
from app.db import session as db_session
from app.db.models.budget import EXPENSE_CATEGORIES, BudgetItem, BudgetPosition
from app.db.models.document import Document
from app.db.models.drive_state import DriveUnlinkedPath
from app.db.models.project import Project
from app.db.models.purchase import PurchaseProcess
from app.services.audit import record_event
from app.services.drive_scan import (
    _ITEM_RE,
    CATEGORY_FOLDER_NAMES,
    CATEGORY_FOLDERS,
    UNNUMBERED_PREFIX,
    fold,
    is_unnumbered_folder,
)

logger = logging.getLogger("financeiro.drive_write")

# Status da cópia de um anexo no drive (Document.drive_copy_status)
COPY_NONE = ""
COPY_PENDING = "pendente"
COPY_DONE = "copiado"
COPY_ERROR = "erro"

TITLE_MAX = 60  # caminhos do projeto já passam de 260 caracteres
FILENAME_MAX = 120
# Um upload recém-feito ainda está com a cópia em andamento (tarefa em
# segundo plano) — a nova tentativa automática espera este tempo.
RETRY_MIN_AGE = timedelta(minutes=2)

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

# Escritas do mesmo processo do servidor em fila: a cópia em segundo plano de
# um upload e a nova tentativa automática nunca escolhem o mesmo nome juntas.
_write_lock = threading.Lock()


def drive_write_enabled() -> bool:
    return settings.drive_write and drive_configured()


def sanitize_name(text: str, max_len: int = TITLE_MAX) -> str:
    """Nome de pasta/arquivo aceito pelo Windows: sem `<>:"/\\|?*` nem
    caracteres de controle, sem ponto/espaço no fim, com tamanho limitado."""
    name = _INVALID.sub(" ", text or "")
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len]
    name = name.rstrip(" .")
    if name.split(".")[0].upper() in _RESERVED:
        name = f"{name}_"
    return name


def sanitize_file_name(filename: str) -> str:
    base = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem, ext = os.path.splitext(base)
    ext = sanitize_name(ext, 12)
    stem = sanitize_name(stem, FILENAME_MAX) or "arquivo"
    return f"{stem}{ext}" if ext and ext != "." else stem


def process_folder_name(process: PurchaseProcess) -> str:
    """`<AAAA-N> <título>` com nº; sem nº, `SEM NUMERO <dd-mm-aaaa> <título>`
    (data de criação do processo — escolha do mantenedor)."""
    title = sanitize_name(process.title) or "Processo"
    if process.process_number:
        number = sanitize_name(process.process_number, 20)
        return f"{number} {title}"
    created = process.created_at or datetime.now(timezone.utc)
    return f"{UNNUMBERED_PREFIX} {created:%d-%m-%Y} {title}"


def _children(backend: DriveBackend, path: str) -> list[DriveEntry]:
    """Primeiro nível de uma pasta do drive; pasta inexistente = vazia."""
    try:
        return backend.list_tree(path, recursive=False)
    except DriveNotFound:
        return []


def _name(entry: DriveEntry) -> str:
    return entry.path.rsplit("/", 1)[-1]


def _item_description(session: Session, project: Project, position: BudgetPosition) -> str:
    query = select(BudgetItem).where(BudgetItem.position_id == position.id)
    items = session.exec(query).all()
    active = [i for i in items if i.revision_id == project.active_revision_id]
    chosen = active[0] if active else (max(items, key=lambda i: i.id or 0) if items else None)
    return chosen.description if chosen else ""


def _claimed_folders(session: Session, project_id: int, except_id: int | None) -> set[str]:
    return {
        p.drive_rel_path.casefold()
        for p in session.exec(select(PurchaseProcess).where(PurchaseProcess.project_id == project_id))
        if p.drive_rel_path and p.id != except_id
    }


def _free_folder(parent: str, name: str, claimed: set[str]) -> str:
    """`parent/name`, ou `parent/name (2)`... se o nome já for de OUTRO
    processo. Uma pasta que existe e não é de ninguém é aproveitada (ex.
    alguém a criou à mão para este processo)."""
    candidate = name
    k = 2
    while f"{parent}/{candidate}".casefold() in claimed:
        candidate = f"{name} ({k})"
        k += 1
    return f"{parent}/{candidate}"


def free_file_name(existing: set[str], name: str) -> str:
    """`name` se estiver livre na pasta (comparação sem diferenciar
    maiúsculas, como no Windows), senão `nome (2).ext`, `(3)`..."""
    if name.casefold() not in existing:
        return name
    stem, ext = os.path.splitext(name)
    k = 2
    while f"{stem} ({k}){ext}".casefold() in existing:
        k += 1
    return f"{stem} ({k}){ext}"


def ensure_process_folder(
    session: Session, project: Project, process: PurchaseProcess, backend: DriveBackend | None = None
) -> str:
    """Pasta do processo no drive, relativa à pasta do projeto — a que ele
    já tem (`drive_rel_path`) ou uma nova (só o caminho: a pasta nasce com o
    primeiro arquivo). Grava `process.drive_rel_path` (sem commit)."""
    if process.drive_rel_path:
        return process.drive_rel_path
    backend = backend or get_drive_backend()
    proj = project_folder(project.drive_folder)
    position = session.get(BudgetPosition, process.budget_position_id)
    if position is None:
        raise DriveError("O processo não está ligado a um item do orçamento.")

    # pasta da categoria: a que já existe (pelo nome, como na leitura), senão a canônica
    top = [e for e in backend.list_tree(proj, recursive=False) if e.is_dir]
    canonical = CATEGORY_FOLDER_NAMES.get(position.category) or sanitize_name(
        str(EXPENSE_CATEGORIES.get(position.category, {}).get("label", position.category)).replace("—", "-")
    )
    matches = [_name(e) for e in top if CATEGORY_FOLDERS.get(fold(_name(e))) == position.category]
    matches.sort(key=lambda n: (fold(n) != fold(canonical), n.casefold()))
    category_folder = matches[0] if matches else canonical

    # pasta do item: "Item N - ..." com o nº do item, senão uma nova com a descrição do orçamento
    item_folder = None
    if matches:
        for entry in sorted(_children(backend, join_rel(proj, category_folder)), key=lambda e: _name(e).casefold()):
            m = _ITEM_RE.match(_name(entry))
            if entry.is_dir and m and int(m.group(1)) == position.item_number:
                item_folder = _name(entry)
                break
    if item_folder is None:
        description = sanitize_name(_item_description(session, project, position)) or "sem descrição"
        item_folder = f"Item {position.item_number} - {description}"

    parent = f"{category_folder}/{item_folder}"
    folder = _free_folder(parent, process_folder_name(process), _claimed_folders(session, project.id, process.id))
    process.drive_rel_path = folder
    session.add(process)
    return folder


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _set_copy(doc: Document, status: str, error: str | None = None) -> None:
    doc.drive_copy_status = status
    doc.drive_copy_error = error


def copy_document(session: Session, doc: Document, backend: DriveBackend | None = None) -> str:
    """Copia um anexo para a pasta do seu processo no drive. Devolve o novo
    status (e o grava). Nunca levanta erro do drive: ele vira o status."""
    with _write_lock:
        return _copy_document(session, doc, backend)


def _copy_document(session: Session, doc: Document, backend: DriveBackend | None) -> str:
    process = session.get(PurchaseProcess, doc.purchase_process_id) if doc.purchase_process_id else None
    project = session.get(Project, process.project_id) if process else None
    if doc.storage_kind != "upload" or project is None or not project.drive_folder or not drive_write_enabled():
        _set_copy(doc, COPY_NONE)
        session.add(doc)
        session.commit()
        return COPY_NONE
    try:
        backend = backend or get_drive_backend()
        proj = project_folder(project.drive_folder)
        folder = ensure_process_folder(session, project, process, backend)
        session.commit()

        if doc.drive_copy_path:
            # Tentativa anterior pode ter gravado sem confirmar (agente lento):
            # se o arquivo está lá, com o mesmo tamanho, já está copiado.
            target = join_rel(proj, doc.drive_copy_path)
            parent = target.rsplit("/", 1)[0]
            if any(
                e.path.casefold() == target.casefold() and not e.is_dir and e.size == doc.size_bytes
                for e in _children(backend, parent)
            ):
                return _copied(session, project, process, doc)

        try:
            with open(resolve_path(doc.storage_path), "rb") as handle:
                data = handle.read()
        except OSError:
            _set_copy(doc, COPY_ERROR, "O arquivo enviado não está mais no servidor.")
            session.add(doc)
            session.commit()
            return COPY_ERROR

        existing = {_name(e).casefold() for e in _children(backend, join_rel(proj, folder))}
        name = free_file_name(existing, sanitize_file_name(doc.original_filename))
        doc.drive_copy_path = f"{folder}/{name}"
        _set_copy(doc, COPY_PENDING)
        session.add(doc)
        session.commit()  # o nome escolhido fica registrado antes de gravar
        backend.write_bytes(join_rel(proj, doc.drive_copy_path), data)
    except DriveUnavailable as exc:
        session.rollback()
        _set_copy(doc, COPY_PENDING, str(exc))
    except DriveFileExists:
        # alguém pôs um arquivo com o mesmo nome entre a conferência e a gravação
        session.rollback()
        doc.drive_copy_path = None
        _set_copy(doc, COPY_PENDING, "Nome ocupado na pasta — tento de novo com outro nome.")
    except (DriveError, OSError) as exc:
        session.rollback()
        _set_copy(doc, COPY_ERROR, str(exc))
    else:
        return _copied(session, project, process, doc)
    session.add(doc)
    session.commit()
    return doc.drive_copy_status


def _copied(session: Session, project: Project, process: PurchaseProcess, doc: Document) -> str:
    _set_copy(doc, COPY_DONE)
    session.add(doc)
    record_event(
        session,
        project_id=project.id,
        entity_type="purchase_process",
        entity_id=process.id,
        action="documento_copiado_para_o_drive",
        actor=None,
        detail={"documento_id": doc.id, "arquivo": doc.original_filename, "no_drive": doc.drive_copy_path},
    )
    session.commit()
    return COPY_DONE


def copy_document_task(doc_id: int) -> None:
    """Tarefa em segundo plano depois do upload (sessão própria)."""
    try:
        with Session(db_session.engine) as session:
            doc = session.get(Document, doc_id)
            if doc is not None:
                copy_document(session, doc)
    except Exception:  # noqa: BLE001 — segundo plano: nunca derruba nada
        logger.exception("Falha ao copiar o documento %s para o drive", doc_id)


def mark_rename_if_needed(process: PurchaseProcess) -> bool:
    """O processo acabou de ganhar o nº e a pasta dele ainda é "SEM NUMERO
    ...": marca para renomear (feito em segundo plano — `rename_process_folder`)."""
    if (
        drive_write_enabled()
        and process.process_number
        and process.drive_rel_path
        and is_unnumbered_folder(process.drive_rel_path.rsplit("/", 1)[-1])
    ):
        process.drive_rename_pending = True
        return True
    return False


def _reprefix(path: str | None, old: str, new: str) -> str | None:
    if path and path.startswith(old + "/"):
        return new + path[len(old):]
    return path


def rename_process_folder(session: Session, process: PurchaseProcess, backend: DriveBackend | None = None) -> bool:
    """Passa os arquivos da pasta "SEM NUMERO ..." para "<AAAA-N> <título>"
    (um único `move_files`, tudo ou nada) e atualiza os caminhos guardados.
    Devolve se terminou; se o drive não respondeu, fica marcado para a
    próxima tentativa."""
    with _write_lock:
        return _rename_process_folder(session, process, backend)


def _rename_process_folder(session: Session, process: PurchaseProcess, backend: DriveBackend | None) -> bool:
    old = process.drive_rel_path
    if not old or not process.process_number or not is_unnumbered_folder(old.rsplit("/", 1)[-1]):
        if process.drive_rename_pending:
            process.drive_rename_pending = False
            session.add(process)
            session.commit()
        return True
    project = session.get(Project, process.project_id)
    if project is None or not project.drive_folder or not drive_write_enabled():
        return False
    try:
        backend = backend or get_drive_backend()
        proj = project_folder(project.drive_folder)
        parent = old.rsplit("/", 1)[0] if "/" in old else ""
        new = _free_folder(parent, process_folder_name(process), _claimed_folders(session, project.id, process.id))
        new = new.lstrip("/")
        old_abs, new_abs = join_rel(proj, old), join_rel(proj, new)
        try:
            entries = backend.list_tree(old_abs, recursive=True)
        except DriveNotFound:
            entries = []  # a pasta nunca chegou a ser criada: só muda o caminho
        moves = [(e.path, new_abs + e.path[len(old_abs):]) for e in entries if not e.is_dir]
        if moves:
            backend.move_files(moves)
        # sobras vazias (só no modo local; o agente não apaga pastas)
        for d in sorted((e.path for e in entries if e.is_dir), key=len, reverse=True):
            backend.remove_empty_dir(d)
        backend.remove_empty_dir(old_abs)
    except DriveUnavailable:
        session.rollback()
        return False
    except (DriveError, OSError) as exc:
        session.rollback()
        logger.warning("Não foi possível renomear a pasta do processo %s no drive: %s", process.id, exc)
        return False

    for doc in session.exec(select(Document).where(Document.purchase_process_id == process.id)):
        if doc.storage_kind == "drive":
            doc.storage_path = _reprefix(doc.storage_path, old, new) or doc.storage_path
        doc.drive_copy_path = _reprefix(doc.drive_copy_path, old, new)
        session.add(doc)
    for unlinked in session.exec(select(DriveUnlinkedPath).where(DriveUnlinkedPath.project_id == project.id)):
        if unlinked.rel_path.startswith(old + "/"):
            unlinked.rel_path = new + unlinked.rel_path[len(old):]
            session.add(unlinked)
    process.drive_rel_path = new
    process.drive_rename_pending = False
    process.updated_at = datetime.now(timezone.utc)
    session.add(process)
    record_event(
        session,
        project_id=project.id,
        entity_type="purchase_process",
        entity_id=process.id,
        action="pasta_renomeada_no_drive",
        actor=None,
        detail={"de": old, "para": new, "arquivos": len(moves)},
    )
    session.commit()
    return True


def rename_process_folder_task(process_id: int) -> None:
    try:
        with Session(db_session.engine) as session:
            process = session.get(PurchaseProcess, process_id)
            if process is not None and process.drive_rename_pending:
                rename_process_folder(session, process)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao renomear a pasta do processo %s no drive", process_id)


def retry_pending(session: Session, backend: DriveBackend | None = None) -> dict[str, int]:
    """Tenta de novo as cópias pendentes/com erro e as pastas a renomear
    (parte da sincronização automática). Renomeia antes de copiar: a cópia
    vai para a pasta já com o nº."""
    if not drive_write_enabled():
        return {"copias": 0, "copias_pendentes": 0, "pastas_renomeadas": 0}
    backend = backend or get_drive_backend()
    renamed = 0
    for process in session.exec(select(PurchaseProcess).where(PurchaseProcess.drive_rename_pending == True)).all():  # noqa: E712
        if rename_process_folder(session, process, backend):
            renamed += 1
    cutoff = datetime.now(timezone.utc) - RETRY_MIN_AGE
    copied = still = 0
    docs = session.exec(
        select(Document).where(
            Document.drive_copy_status.in_([COPY_PENDING, COPY_ERROR]),  # type: ignore[attr-defined]
            Document.purchase_process_id.is_not(None),  # type: ignore[union-attr]
        )
    ).all()
    for doc in docs:
        if _as_utc(doc.uploaded_at) > cutoff:
            continue  # a cópia do próprio upload ainda pode estar em andamento
        if copy_document(session, doc, backend) == COPY_DONE:
            copied += 1
        else:
            still += 1
    return {"copias": copied, "copias_pendentes": still, "pastas_renomeadas": renamed}


def unlink_paths(session: Session, project_id: int, paths: list[str], username: str) -> None:
    """Registra arquivos do drive que não devem voltar a ser vinculados pela
    sincronização (documento desvinculado ou anexo removido no módulo)."""
    known = {
        u.rel_path
        for u in session.exec(select(DriveUnlinkedPath).where(DriveUnlinkedPath.project_id == project_id))
    }
    for path in paths:
        if path and path not in known:
            session.add(DriveUnlinkedPath(project_id=project_id, rel_path=path, unlinked_by_username=username))
            known.add(path)
