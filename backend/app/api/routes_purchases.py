"""Processo de compra: criação, transição de estado (único ponto de
entrada — ver services/transitions.py) e documentos anexados.
"""

from __future__ import annotations

import os
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.drive import DriveError
from app.core.files import delete_file, read_upload_limited, resolve_document_path, save_upload
from app.core.identity import HorunIdentity, get_identity
from app.core.money import round_money
from app.core.permissions import get_membership
from app.core.process_number import normalize_process_number
from app.core.redaction import money
from app.db.models.budget import EXPENSE_CATEGORIES, BudgetPosition
from app.db.models.document import DOC_TYPES, MAX_QUOTES_PER_PROCESS, Document
from app.db.models.project import Project, ProjectMembership
from app.db.models.purchase import PRE_AUTHORIZATION_STATES, TERMINAL_STATES, PurchaseProcess
from app.db.session import get_session
from app.schemas.purchase import (
    AvailabilityCheckOut,
    AvailabilityCheckRequest,
    DocumentOut,
    DocumentTypeUpdate,
    PurchaseProcessCreate,
    PurchaseProcessOut,
    PurchaseProcessUpdate,
    TransitionRequest,
)
from app.services.audit import record_event
from app.services.balance import brl, check_balance, position_balance
from app.services.transitions import TransitionError, apply_transition

router = APIRouter(prefix="/projects/{project_id}/purchase-processes", tags=["purchases"])


def _get_process(session: Session, project_id: int, process_id: int) -> PurchaseProcess:
    process = session.get(PurchaseProcess, process_id)
    if process is None or process.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo de compra não encontrado.")
    return process


def _balance_warnings(
    session: Session,
    project_id: int,
    position_id: int,
    additional: Decimal,
    origin: str = "manual",
    *,
    show_values: bool = True,
) -> list[str]:
    """Aplica a política de saldo do projeto: "bloquear" recusa a operação
    (409, com a mensagem pronta para o usuário); "avisar" deixa passar e
    devolve o aviso. Processos vindos do drive (histórico já consumado) nunca
    são bloqueados — só avisados."""
    project = session.get(Project, project_id)
    message = check_balance(session, project, position_id, additional, show_values=show_values)
    if message is None:
        return []
    if project.balance_policy == "bloquear" and origin != "drive_import":
        raise HTTPException(status.HTTP_409_CONFLICT, message)
    return [message]


def _out(process: PurchaseProcess, warnings: list[str] | None = None, *, visible: bool) -> PurchaseProcessOut:
    """`visible=False` (quem não é coordenador) esconde os valores em R$ —
    ver core/redaction.py. Os avisos já vêm sem valores nesse caso
    (`_balance_warnings(show_values=...)`)."""
    out = PurchaseProcessOut.model_validate(process, from_attributes=True)
    out.estimated_unit_value = money(process.estimated_unit_value, visible=visible)
    out.estimated_value = money(process.estimated_value, visible=visible)
    out.final_value = money(process.final_value, visible=visible)
    out.warnings = warnings or []
    return out


def _invoice_over_balance(
    session: Session, process: PurchaseProcess, body: TransitionRequest, *, show_values: bool
) -> str | None:
    """Aviso se a nota fiscal passa do saldo do item, ou None.

    A partir de "autorizado" o processo já conta como realizado pelo valor
    ESTIMADO; com a nota, passa a contar pelo final. O que pode estourar o
    saldo é só a diferença (final − estimado)."""
    if body.action != "emitir_nota_fiscal" or body.final_value is None or process.status != "autorizado":
        return None
    additional = body.final_value - process.estimated_value
    project = session.get(Project, process.project_id)
    message = check_balance(session, project, process.budget_position_id, additional, show_values=show_values)
    if message is None or not show_values:
        return message
    # Com valores: frase própria da nota fiscal — a genérica falaria em
    # "valor solicitado" = só a diferença, o que confunde aqui.
    row = position_balance(session, process.project_id, process.budget_position_id)
    if row is None:
        return message
    available = max(row.balance, Decimal("0"))
    return (
        f"A nota fiscal de {brl(body.final_value)} fica {brl(additional)} acima do valor estimado "
        f"({brl(process.estimated_value)}), mas o item Nº {row.item_number} só tem {brl(available)} de saldo "
        f"(faltam {brl(additional - available)})."
    )


def _commit_or_conflict(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe outro processo deste projeto com este nº de processo COPPETEC."
        ) from exc


@router.get("", response_model=list[PurchaseProcessOut])
def list_processes(
    project_id: int,
    category: str | None = None,
    position_id: int | None = None,
    status_filter: str | None = None,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    query = select(PurchaseProcess).where(PurchaseProcess.project_id == project_id)
    if position_id is not None:
        query = query.where(PurchaseProcess.budget_position_id == position_id)
    if status_filter is not None:
        query = query.where(PurchaseProcess.status == status_filter)
    if category is not None:
        query = query.where(
            PurchaseProcess.budget_position_id.in_(  # type: ignore[attr-defined]
                select(BudgetPosition.id).where(
                    BudgetPosition.project_id == project_id, BudgetPosition.category == category
                )
            )
        )
    processes = list(session.exec(query))
    processes.sort(key=lambda p: p.created_at, reverse=True)
    visible = membership.role == "coordenador"
    return [_out(p, visible=visible) for p in processes]


@router.post("", response_model=PurchaseProcessOut, status_code=status.HTTP_201_CREATED)
def create_process(
    project_id: int,
    body: PurchaseProcessCreate,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    position = session.get(BudgetPosition, body.budget_position_id)
    if position is None or position.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item de orçamento não encontrado.")
    if EXPENSE_CATEGORIES[position.category]["is_personnel"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Equipe Executora não usa o fluxo de compra — lance uma atribuição de pessoal.",
        )
    if body.previous_attempt_id is not None:
        previous = _get_process(session, project_id, body.previous_attempt_id)
        if previous.status not in ("cancelado", "rejeitado"):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Só é possível referenciar uma tentativa cancelada ou rejeitada.",
            )

    estimated_value = round_money(body.quantity * body.estimated_unit_value)
    warnings = _balance_warnings(
        session, project_id, position.id, estimated_value, show_values=membership.role == "coordenador"
    )

    process = PurchaseProcess(
        project_id=project_id,
        budget_position_id=body.budget_position_id,
        title=body.title,
        vendor=body.vendor,
        quantity=body.quantity,
        estimated_unit_value=body.estimated_unit_value,
        estimated_value=estimated_value,
        asset_registration_flag=body.asset_registration_flag,
        previous_attempt_id=body.previous_attempt_id,
        created_by_user_id=identity.user_id,
        created_by_username=identity.username,
    )
    session.add(process)
    session.flush()
    record_event(
        session,
        project_id=project_id,
        entity_type="purchase_process",
        entity_id=process.id,
        action="criado",
        actor=identity,
        detail={"titulo": body.title, "valor_estimado": estimated_value, "avisos": warnings},
    )
    session.commit()
    session.refresh(process)
    return _out(process, warnings, visible=membership.role == "coordenador")


@router.post("/check-availability", response_model=AvailabilityCheckOut)
def check_availability(
    project_id: int,
    body: AvailabilityCheckRequest,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    """Responde só sim/não — nunca o saldo real, mesmo pra quem não é
    coordenador (ver core/redaction.py). É o que deixa o operador comum
    conferir se um valor cabe no orçamento sem nunca ver o número."""
    position = session.get(BudgetPosition, body.budget_position_id)
    if position is None or position.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item de orçamento não encontrado.")

    balance = position_balance(session, project_id, body.budget_position_id)
    if balance is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Projeto não tem revisão orçamentária ativa.")

    estimated = round_money(body.quantity * body.estimated_unit_value)
    return AvailabilityCheckOut(available=(balance.balance - estimated) >= 0)


@router.get("/{process_id}", response_model=PurchaseProcessOut)
def get_process(
    project_id: int,
    process_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    return _out(process, visible=membership.role == "coordenador")


@router.patch("/{process_id}", response_model=PurchaseProcessOut)
def update_process(
    project_id: int,
    process_id: int,
    body: PurchaseProcessUpdate,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    if process.status in TERMINAL_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Processo encerrado não pode mais ser editado.")
    if process.status not in PRE_AUTHORIZATION_STATES and membership.role != "coordenador":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só o coordenador pode editar um processo já autorizado."
        )

    data = body.model_dump(exclude_unset=True)
    if "process_number" in data:
        data["process_number"] = normalize_process_number(data["process_number"])
        if data["process_number"] is not None:
            clash = session.exec(
                select(PurchaseProcess).where(
                    PurchaseProcess.project_id == project_id,
                    PurchaseProcess.process_number == data["process_number"],
                    PurchaseProcess.id != process.id,
                )
            ).first()
            if clash is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"O processo {data['process_number']} já está cadastrado neste projeto (\"{clash.title}\").",
                )

    warnings: list[str] = []
    if "quantity" in data or "estimated_unit_value" in data:
        new_estimated = round_money(
            data.get("quantity", process.quantity)
            * data.get("estimated_unit_value", process.estimated_unit_value)
        )
        # Com valor final (nota fiscal) já lançado, o saldo usa ele — editar a
        # estimativa não muda mais nada, então não há o que checar.
        if process.final_value is None:
            warnings = _balance_warnings(
                session, project_id, process.budget_position_id,
                new_estimated - process.estimated_value, process.origin,
                show_values=membership.role == "coordenador",
            )

    changes = {
        field: [getattr(process, field), value]
        for field, value in data.items()
        if getattr(process, field) != value
    }
    for field, value in data.items():
        setattr(process, field, value)
    if "quantity" in data or "estimated_unit_value" in data:
        process.estimated_value = round_money(process.quantity * process.estimated_unit_value)
    session.add(process)
    if changes:
        record_event(
            session,
            project_id=project_id,
            entity_type="purchase_process",
            entity_id=process.id,
            action="editado",
            actor=identity,
            detail={"campos": changes, "avisos": warnings},
        )
    _commit_or_conflict(session)
    session.refresh(process)
    return _out(process, warnings, visible=membership.role == "coordenador")


@router.post("/{process_id}/transition", response_model=PurchaseProcessOut)
def transition_process(
    project_id: int,
    process_id: int,
    body: TransitionRequest,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    is_coordenador = membership.role == "coordenador"
    over_balance_warning = _invoice_over_balance(session, process, body, show_values=is_coordenador)
    if over_balance_warning is not None and not body.confirm_over_balance:
        # 428: o frontend mostra o aviso e pergunta; confirmando, reenvia com
        # confirm_over_balance=true. Vale para qualquer política de saldo —
        # a nota fiscal é um fato, não se bloqueia, só se registra o alerta.
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            f"{over_balance_warning} Confirme para registrar a nota fiscal mesmo assim.",
        )
    try:
        updated = apply_transition(
            session,
            process,
            action=body.action,
            is_coordenador=membership.role == "coordenador",
            reason=body.reason,
            vendor=body.vendor,
            process_number=body.process_number,
            final_value=body.final_value,
            actor=identity,
            override_reason=body.override_reason,
            over_balance_warning=over_balance_warning,
        )
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _out(updated, visible=membership.role == "coordenador")


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        original_filename=doc.original_filename,
        storage_kind=doc.storage_kind,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        period_label=doc.period_label,
        note=doc.note,
        uploaded_by_username=doc.uploaded_by_username,
        uploaded_at=doc.uploaded_at,
    )


@router.get("/{process_id}/documents", response_model=list[DocumentOut])
def list_documents(
    project_id: int,
    process_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_process(session, project_id, process_id)
    docs = session.exec(select(Document).where(Document.purchase_process_id == process_id))
    return [_doc_out(d) for d in docs]


@router.post("/{process_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: int,
    process_id: int,
    doc_type: str = Form(...),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    if process.status in TERMINAL_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Processo encerrado não aceita novos documentos.")
    if doc_type not in DOC_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo de documento inválido.")
    if doc_type == "cotacao":
        existing = session.exec(
            select(Document).where(
                Document.purchase_process_id == process_id, Document.doc_type == "cotacao"
            )
        ).all()
        if len(existing) >= MAX_QUOTES_PER_PROCESS:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Máximo de {MAX_QUOTES_PER_PROCESS} cotações por processo."
            )

    content, sha256 = await read_upload_limited(file)
    storage_path, size = save_upload(project_id, "purchases", process_id, file.filename or "arquivo", content)
    document = Document(
        purchase_process_id=process_id,
        doc_type=doc_type,
        original_filename=file.filename or "arquivo",
        storage_path=storage_path,
        storage_kind="upload",
        sha256=sha256,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        note=note,
        uploaded_by_user_id=identity.user_id,
        uploaded_by_username=identity.username,
    )
    session.add(document)
    session.flush()
    record_event(
        session,
        project_id=project_id,
        entity_type="purchase_process",
        entity_id=process_id,
        action="documento_enviado",
        actor=identity,
        detail={"documento_id": document.id, "tipo": doc_type, "arquivo": document.original_filename, "sha256": sha256},
    )
    session.commit()
    session.refresh(document)
    return _doc_out(document)


@router.patch("/{process_id}/documents/{doc_id}", response_model=DocumentOut)
def reclassify_document(
    project_id: int,
    process_id: int,
    doc_id: int,
    body: DocumentTypeUpdate,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    """Corrige o tipo de um documento — útil para os do drive, cujo tipo é
    inferido pelo nome do arquivo. Só metadado: vale mesmo em processo
    encerrado, e fica no histórico."""
    _get_process(session, project_id, process_id)
    doc = session.get(Document, doc_id)
    if doc is None or doc.purchase_process_id != process_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo de documento inválido.")
    previous = doc.doc_type
    doc.doc_type = body.doc_type
    session.add(doc)
    record_event(
        session,
        project_id=project_id,
        entity_type="purchase_process",
        entity_id=process_id,
        action="documento_reclassificado",
        actor=identity,
        detail={"documento_id": doc.id, "de": previous, "para": body.doc_type},
    )
    session.commit()
    session.refresh(doc)
    return _doc_out(doc)


@router.get("/{process_id}/documents/{doc_id}/download")
def download_document(
    project_id: int,
    process_id: int,
    doc_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_process(session, project_id, process_id)
    doc = session.get(Document, doc_id)
    if doc is None or doc.purchase_process_id != process_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    project = session.get(Project, project_id)
    try:
        path = resolve_document_path(project, doc)
    except DriveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado no armazenamento.")
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_filename)


@router.delete("/{process_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    project_id: int,
    process_id: int,
    doc_id: int,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    doc = session.get(Document, doc_id)
    if doc is None or doc.purchase_process_id != process_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    if process.status in TERMINAL_STATES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Processo encerrado — documentos ficam retidos para auditoria."
        )
    if doc.uploaded_by_user_id != identity.user_id and membership.role != "coordenador":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só quem enviou o documento ou o coordenador pode removê-lo."
        )
    # Documento do drive: só desfaz o vínculo — o arquivo é do drive e nunca é
    # apagado por este módulo.
    if doc.storage_kind == "upload":
        delete_file(doc.storage_path)
    record_event(
        session,
        project_id=project_id,
        entity_type="purchase_process",
        entity_id=process_id,
        action="documento_removido",
        actor=identity,
        detail={"documento_id": doc.id, "tipo": doc.doc_type, "arquivo": doc.original_filename, "origem": doc.storage_kind},
    )
    session.delete(doc)
    session.commit()
