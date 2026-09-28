"""Equipe Executora: pessoas, atribuições (acúmulo calculado, nunca
armazenado — ver services/accrual.py) e recibos mensais anexados.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.files import delete_file, resolve_path, save_upload
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador
from app.db.models.budget import EXPENSE_CATEGORIES, BudgetPosition
from app.db.models.document import Document
from app.db.models.personnel import Person, PersonnelAssignment
from app.db.models.project import ProjectMembership
from app.db.session import get_session
from app.schemas.purchase import DocumentOut
from app.schemas.personnel import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentUpdate,
    CloseAssignmentRequest,
    PersonCreate,
    PersonOut,
)
from app.services.accrual import compute_accrual

router = APIRouter(prefix="/projects/{project_id}", tags=["personnel"])


@router.get("/personnel", response_model=list[PersonOut])
def list_people(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    return session.exec(select(Person).where(Person.project_id == project_id)).all()


@router.post("/personnel", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(
    project_id: int,
    body: PersonCreate,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    person = Person(project_id=project_id, full_name=body.full_name, cpf=body.cpf)
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def _assignment_out(session: Session, assignment: PersonnelAssignment, person: Person) -> AssignmentOut:
    accrual = compute_accrual(
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        status=assignment.status,
        monthly_rate=assignment.monthly_rate,
        today=date.today(),
    )
    return AssignmentOut(
        id=assignment.id,
        project_id=assignment.project_id,
        person_id=assignment.person_id,
        person_name=person.full_name,
        budget_position_id=assignment.budget_position_id,
        role_title=assignment.role_title,
        monthly_rate=assignment.monthly_rate,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        status=assignment.status,
        accrued_months=accrual.accrued_months,
        accrued_value=accrual.accrued_value,
        committed_future_value=accrual.committed_future_value,
    )


def _get_assignment(session: Session, project_id: int, assignment_id: int) -> PersonnelAssignment:
    assignment = session.get(PersonnelAssignment, assignment_id)
    if assignment is None or assignment.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Atribuição não encontrada.")
    return assignment


@router.get("/personnel-assignments", response_model=list[AssignmentOut])
def list_assignments(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    assignments = session.exec(
        select(PersonnelAssignment).where(PersonnelAssignment.project_id == project_id)
    ).all()
    people = {p.id: p for p in session.exec(select(Person).where(Person.project_id == project_id))}
    return [_assignment_out(session, a, people[a.person_id]) for a in assignments]


@router.post("/personnel-assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    project_id: int,
    body: AssignmentCreate,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    person = session.get(Person, body.person_id)
    if person is None or person.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pessoa não encontrada.")

    position = session.get(BudgetPosition, body.budget_position_id)
    if position is None or position.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item de orçamento não encontrado.")
    if not EXPENSE_CATEGORIES[position.category]["is_personnel"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Atribuições de pessoal só podem ser lançadas contra um item da categoria Equipe Executora.",
        )

    assignment = PersonnelAssignment(
        project_id=project_id,
        person_id=body.person_id,
        budget_position_id=body.budget_position_id,
        role_title=body.role_title,
        monthly_rate=body.monthly_rate,
        start_date=body.start_date,
        created_by_user_id=identity.user_id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return _assignment_out(session, assignment, person)


@router.patch("/personnel-assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    project_id: int,
    assignment_id: int,
    body: AssignmentUpdate,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    assignment = _get_assignment(session, project_id, assignment_id)
    if assignment.status == "encerrado":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Atribuição encerrada não pode mais ser editada — reabra uma nova atribuição se for o caso.",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    person = session.get(Person, assignment.person_id)
    return _assignment_out(session, assignment, person)


@router.post("/personnel-assignments/{assignment_id}/close", response_model=AssignmentOut)
def close_assignment(
    project_id: int,
    assignment_id: int,
    body: CloseAssignmentRequest,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    assignment = _get_assignment(session, project_id, assignment_id)
    if assignment.status == "encerrado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Atribuição já está encerrada.")
    if body.end_date < assignment.start_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data de fim anterior à data de início.")
    if body.end_date > date.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Data de fim não pode ser no futuro — feche a atribuição só quando ela já tiver terminado "
            "(um fim futuro já combinado conta como comprometido, não como encerrado).",
        )
    assignment.status = "encerrado"
    assignment.end_date = body.end_date
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    person = session.get(Person, assignment.person_id)
    return _assignment_out(session, assignment, person)


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


@router.get("/personnel-assignments/{assignment_id}/documents", response_model=list[DocumentOut])
def list_assignment_documents(
    project_id: int,
    assignment_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_assignment(session, project_id, assignment_id)
    docs = session.exec(
        select(Document).where(Document.personnel_assignment_id == assignment_id)
    )
    return [_doc_out(d) for d in docs]


@router.post(
    "/personnel-assignments/{assignment_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_assignment_document(
    project_id: int,
    assignment_id: int,
    period_label: str | None = Form(None),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_assignment(session, project_id, assignment_id)
    content = await file.read()
    storage_path, size = save_upload(project_id, "personnel", assignment_id, file.filename or "arquivo", content)
    document = Document(
        personnel_assignment_id=assignment_id,
        doc_type="recibo_pessoal",
        original_filename=file.filename or "arquivo",
        storage_path=storage_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        period_label=period_label,
        note=note,
        uploaded_by_user_id=identity.user_id,
        uploaded_by_username=identity.username,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return _doc_out(document)


@router.get("/personnel-assignments/{assignment_id}/documents/{doc_id}/download")
def download_assignment_document(
    project_id: int,
    assignment_id: int,
    doc_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_assignment(session, project_id, assignment_id)
    doc = session.get(Document, doc_id)
    if doc is None or doc.personnel_assignment_id != assignment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    path = resolve_path(doc.storage_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado no armazenamento.")
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_filename)


@router.delete("/personnel-assignments/{assignment_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment_document(
    project_id: int,
    assignment_id: int,
    doc_id: int,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    assignment = _get_assignment(session, project_id, assignment_id)
    doc = session.get(Document, doc_id)
    if doc is None or doc.personnel_assignment_id != assignment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    if assignment.status == "encerrado":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Atribuição encerrada — documentos ficam retidos para auditoria."
        )
    if doc.uploaded_by_user_id != identity.user_id and membership.role != "coordenador":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só quem enviou o documento ou o coordenador pode removê-lo."
        )
    delete_file(doc.storage_path)
    session.delete(doc)
    session.commit()
