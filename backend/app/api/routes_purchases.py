"""Processo de compra: criação, transição de estado (único ponto de
entrada — ver services/transitions.py) e documentos anexados.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.files import delete_file, resolve_path, save_upload
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership
from app.core.redaction import money
from app.db.models.budget import EXPENSE_CATEGORIES, BudgetPosition
from app.db.models.document import DOC_TYPES, MAX_QUOTES_PER_PROCESS, Document
from app.db.models.project import ProjectMembership
from app.db.models.purchase import PRE_AUTHORIZATION_STATES, TERMINAL_STATES, PurchaseProcess
from app.db.session import get_session
from app.schemas.purchase import (
    DocumentOut,
    PurchaseProcessCreate,
    PurchaseProcessOut,
    PurchaseProcessUpdate,
    TransitionRequest,
)
from app.services.transitions import TransitionError, apply_transition

router = APIRouter(prefix="/projects/{project_id}/purchase-processes", tags=["purchases"])


def _get_process(session: Session, project_id: int, process_id: int) -> PurchaseProcess:
    process = session.get(PurchaseProcess, process_id)
    if process is None or process.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo de compra não encontrado.")
    return process


def _process_out(process: PurchaseProcess, *, visible: bool) -> PurchaseProcessOut:
    return PurchaseProcessOut(
        id=process.id,
        project_id=process.project_id,
        budget_position_id=process.budget_position_id,
        process_number=process.process_number,
        title=process.title,
        vendor=process.vendor,
        quantity=process.quantity,
        estimated_unit_value=money(process.estimated_unit_value, visible=visible),
        estimated_value=money(process.estimated_value, visible=visible),
        final_value=money(process.final_value, visible=visible),
        asset_registration_flag=process.asset_registration_flag,
        status=process.status,
        previous_attempt_id=process.previous_attempt_id,
        cancel_reason=process.cancel_reason,
        created_by_username=process.created_by_username,
        created_at=process.created_at,
        updated_at=process.updated_at,
        completed_at=process.completed_at,
        closed_at=process.closed_at,
    )


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
    processes = list(session.exec(query))

    if category is not None:
        position_ids = {
            p.id
            for p in session.exec(
                select(BudgetPosition).where(
                    BudgetPosition.project_id == project_id, BudgetPosition.category == category
                )
            )
        }
        processes = [p for p in processes if p.budget_position_id in position_ids]

    processes.sort(key=lambda p: p.created_at, reverse=True)
    visible = membership.role == "coordenador"
    return [_process_out(p, visible=visible) for p in processes]


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

    process = PurchaseProcess(
        project_id=project_id,
        budget_position_id=body.budget_position_id,
        title=body.title,
        vendor=body.vendor,
        quantity=body.quantity,
        estimated_unit_value=body.estimated_unit_value,
        estimated_value=body.quantity * body.estimated_unit_value,
        asset_registration_flag=body.asset_registration_flag,
        previous_attempt_id=body.previous_attempt_id,
        created_by_user_id=identity.user_id,
        created_by_username=identity.username,
    )
    session.add(process)
    session.commit()
    session.refresh(process)
    return _process_out(process, visible=membership.role == "coordenador")


@router.get("/{process_id}", response_model=PurchaseProcessOut)
def get_process(
    project_id: int,
    process_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
    return _process_out(process, visible=membership.role == "coordenador")


@router.patch("/{process_id}", response_model=PurchaseProcessOut)
def update_process(
    project_id: int,
    process_id: int,
    body: PurchaseProcessUpdate,
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
    for field, value in data.items():
        setattr(process, field, value)
    if "quantity" in data or "estimated_unit_value" in data:
        process.estimated_value = process.quantity * process.estimated_unit_value
    session.add(process)
    session.commit()
    session.refresh(process)
    return _process_out(process, visible=membership.role == "coordenador")


@router.post("/{process_id}/transition", response_model=PurchaseProcessOut)
def transition_process(
    project_id: int,
    process_id: int,
    body: TransitionRequest,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    process = _get_process(session, project_id, process_id)
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
        )
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _process_out(updated, visible=membership.role == "coordenador")


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        original_filename=doc.original_filename,
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

    content = await file.read()
    storage_path, size = save_upload(project_id, "purchases", process_id, file.filename or "arquivo", content)
    document = Document(
        purchase_process_id=process_id,
        doc_type=doc_type,
        original_filename=file.filename or "arquivo",
        storage_path=storage_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        note=note,
        uploaded_by_user_id=identity.user_id,
        uploaded_by_username=identity.username,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return _doc_out(document)


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
    path = resolve_path(doc.storage_path)
    if not path.exists():
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
    delete_file(doc.storage_path)
    session.delete(doc)
    session.commit()
