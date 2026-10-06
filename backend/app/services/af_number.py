"""Nº do processo lido da autorização de fornecimento (AF) da COPPETEC.

A AF traz impresso "AUTORIZAÇÃO DE COMPRA <AAAA>/<N>" — o mesmo nº da pasta
do processo (AAAA-N). Quando uma AF é anexada no módulo, ou vinculada pela
sincronização a um processo SEM nº, o programa lê o nº do PDF (só as 2
primeiras páginas) e o preenche — e aí a pasta "SEM NUMERO ..." do drive
ganha o nº (services/drive_write.py).

Nunca sobrescreve: processo que já tem OUTRO nº, ou nº que já é de outro
processo do projeto, só gera um aviso (no histórico e na resposta). Falha
de leitura (PDF escaneado sem texto, pypdf ausente, arquivo grande demais,
agente offline) nunca atrapalha nada — só não preenche; a sincronização
automática tenta de novo os processos sem nº que têm AF.
"""

from __future__ import annotations

import io
import logging
import re

from sqlmodel import Session, select

from app.core.config import settings
from app.core.drive import DriveError, DriveUnavailable, join_rel, project_folder
from app.core.drive_backend import DriveBackend, get_drive_backend
from app.core.files import resolve_path
from app.core.identity import HorunIdentity
from app.core.process_number import normalize_process_number
from app.db.models.document import Document
from app.db.models.project import Project
from app.db.models.purchase import PurchaseProcess
from app.services.audit import record_event
from app.services.drive_write import mark_rename_if_needed

logger = logging.getLogger("financeiro.af_number")

AF_DOC_TYPE = "autorizacao_fornecimento"
_AF_RE = re.compile(
    r"AUTORIZA[ÇC][ÃA]O\s+DE\s+COMPRA\s*(?:N[º°o.]*\s*)?(\d{4})\s*/\s*(\d{1,6})", re.IGNORECASE
)
MAX_PAGES = 2

# Documentos já lidos sem achar nº (PDF escaneado...) — não baixar de novo a
# cada rodada automática enquanto o servidor estiver de pé.
_no_number_docs: set[int] = set()


def number_from_text(text: str) -> str | None:
    match = _AF_RE.search(text or "")
    if match is None:
        return None
    return normalize_process_number(f"{match.group(1)}-{match.group(2)}")


def extract_af_number(data: bytes) -> str | None:
    """Nº "AAAA-N" do texto das primeiras páginas, ou None (qualquer falha)."""
    try:
        from pypdf import PdfReader
    except ImportError:  # extra "import" não instalado
        logger.warning("pypdf não instalado: o nº da autorização de fornecimento não é lido.")
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
    except Exception:  # noqa: BLE001 — PDF quebrado/criptografado: só não lê
        logger.info("Não foi possível ler o texto de uma autorização de fornecimento.", exc_info=True)
        return None
    return number_from_text(text)


def apply_af_number(
    session: Session, process: PurchaseProcess, number: str | None, *, filename: str,
    actor: HorunIdentity | None = None,
) -> str | None:
    """Preenche o nº do processo com o da AF, se ele não tiver. Devolve um
    aviso (texto) quando não preenche por conflito. Não faz commit."""
    if not number or process.process_number == number:
        return None
    if process.process_number:
        warning = (
            f"A autorização de fornecimento traz o nº {number}, diferente do cadastrado {process.process_number}."
        )
        _warn(session, process, warning, filename, actor)
        return warning
    clash = session.exec(
        select(PurchaseProcess).where(
            PurchaseProcess.project_id == process.project_id,
            PurchaseProcess.process_number == number,
            PurchaseProcess.id != process.id,
        )
    ).first()
    if clash is not None:
        warning = (
            f"A autorização de fornecimento traz o nº {number}, que já é do processo \"{clash.title}\" — "
            "o nº não foi preenchido."
        )
        _warn(session, process, warning, filename, actor)
        return warning
    process.process_number = number
    mark_rename_if_needed(process)
    session.add(process)
    record_event(
        session,
        project_id=process.project_id,
        entity_type="purchase_process",
        entity_id=process.id,
        action="numero_lido_da_autorizacao",
        actor=actor,
        detail={"numero": number, "arquivo": filename},
    )
    return None


def _warn(session: Session, process: PurchaseProcess, warning: str, filename: str, actor: HorunIdentity | None) -> None:
    record_event(
        session,
        project_id=process.project_id,
        entity_type="purchase_process",
        entity_id=process.id,
        action="numero_da_autorizacao_nao_usado",
        actor=actor,
        detail={"aviso": warning, "arquivo": filename},
    )


def _document_bytes(session: Session, doc: Document, backend: DriveBackend | None) -> bytes | None:
    if doc.storage_kind == "upload":
        try:
            with open(resolve_path(doc.storage_path), "rb") as handle:
                return handle.read()
        except OSError:
            return None
    process = session.get(PurchaseProcess, doc.purchase_process_id)
    project = session.get(Project, process.project_id) if process else None
    if project is None:
        return None
    backend = backend or get_drive_backend()
    return backend.read_bytes(
        join_rel(project_folder(project.drive_folder), doc.storage_path), max_bytes=settings.agent_max_file_bytes
    )


def fill_numbers_from_afs(
    session: Session, project_id: int | None = None, backend: DriveBackend | None = None
) -> int:
    """Processos SEM nº que têm AF anexada ou vinculada: lê o nº do PDF.
    Devolve quantos foram preenchidos. Com o drive fora do ar, para em
    silêncio (a próxima rodada tenta de novo). Faz commit."""
    query = select(PurchaseProcess).where(PurchaseProcess.process_number.is_(None))  # type: ignore[union-attr]
    if project_id is not None:
        query = query.where(PurchaseProcess.project_id == project_id)
    filled = 0
    for process in session.exec(query).all():
        if process.origin == "planilha_sem_numero":
            continue  # lançamento da planilha sem nº: não tem AF
        docs = session.exec(
            select(Document).where(Document.purchase_process_id == process.id, Document.doc_type == AF_DOC_TYPE)
        ).all()
        for doc in docs:
            if doc.id in _no_number_docs:
                continue
            try:
                data = _document_bytes(session, doc, backend)
            except DriveUnavailable:
                return filled
            except DriveError:
                continue  # sumiu do drive, grande demais...
            number = extract_af_number(data) if data else None
            if number is None:
                _no_number_docs.add(doc.id)  # type: ignore[arg-type]
                continue
            apply_af_number(session, process, number, filename=doc.original_filename)
            session.commit()
            if process.process_number == number:
                filled += 1
            break
    return filled


def retry_missing_numbers(session: Session) -> int:
    """Parte da sincronização automática."""
    try:
        return fill_numbers_from_afs(session)
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("Falha ao ler o nº das autorizações de fornecimento")
        return 0


def fill_numbers_task(project_id: int) -> None:
    """Depois da sincronização pelo botão (segundo plano, sessão própria):
    lê o nº das AFs recém-vinculadas e renomeia as pastas "SEM NUMERO"."""
    from app.db import session as db_session
    from app.services.drive_write import rename_process_folder

    try:
        with Session(db_session.engine) as session:
            if fill_numbers_from_afs(session, project_id) == 0:
                return
            pending = session.exec(
                select(PurchaseProcess).where(
                    PurchaseProcess.project_id == project_id,
                    PurchaseProcess.drive_rename_pending == True,  # noqa: E712
                )
            ).all()
            for process in pending:
                rename_process_folder(session, process)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao ler o nº das autorizações do projeto %s", project_id)
