"""Equipe Executora: pessoas, atribuições (acúmulo calculado, nunca
armazenado — ver services/accrual.py) e recibos mensais anexados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.core.files import delete_file, file_response, read_upload_limited, resolve_path, save_upload
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador
from app.core.redaction import money
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
    PersonnelImportPreviewOut,
    PersonnelImportResultOut,
    PersonnelImportRowOut,
    PersonOut,
)
from app.services.accrual import compute_accrual
from app.services.audit import record_event
from app.services.budget_import import BudgetImportError
from app.services.personnel_import import PersonnelSheetResult, parse_personnel_sheet

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


def _assignment_out(
    session: Session, assignment: PersonnelAssignment, person: Person, *, visible: bool
) -> AssignmentOut:
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
        monthly_rate=money(assignment.monthly_rate, visible=visible),
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        status=assignment.status,
        accrued_months=accrual.accrued_months,
        accrued_value=money(accrual.accrued_value, visible=visible),
        committed_future_value=money(accrual.committed_future_value, visible=visible),
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
    membership: ProjectMembership = Depends(get_membership),
):
    assignments = session.exec(
        select(PersonnelAssignment).where(PersonnelAssignment.project_id == project_id)
    ).all()
    people = {p.id: p for p in session.exec(select(Person).where(Person.project_id == project_id))}
    visible = membership.role == "coordenador"
    return [_assignment_out(session, a, people[a.person_id], visible=visible) for a in assignments]


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
    return _assignment_out(session, assignment, person, visible=True)  # rota já é coordenador-only


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
    return _assignment_out(session, assignment, person, visible=True)  # rota já é coordenador-only


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
    return _assignment_out(session, assignment, person, visible=True)  # rota já é coordenador-only


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
    assignment = _get_assignment(session, project_id, assignment_id)
    # Mesma disciplina do upload de compras: atribuição encerrada fica
    # congelada (o delete já recusava), tamanho limitado sem carregar tudo na
    # memória, hash e evento de auditoria — é recibo de pagamento de pessoa.
    if assignment.status == "encerrado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Atribuição encerrada não aceita novos documentos.")
    content, sha256 = await read_upload_limited(file)
    storage_path, size = save_upload(project_id, "personnel", assignment_id, file.filename or "arquivo", content)
    document = Document(
        personnel_assignment_id=assignment_id,
        doc_type="recibo_pessoal",
        original_filename=file.filename or "arquivo",
        storage_path=storage_path,
        storage_kind="upload",
        sha256=sha256,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        period_label=period_label,
        note=note,
        uploaded_by_user_id=identity.user_id,
        uploaded_by_username=identity.username,
    )
    session.add(document)
    session.flush()
    record_event(
        session,
        project_id=project_id,
        entity_type="personnel_assignment",
        entity_id=assignment_id,
        action="documento_enviado",
        actor=identity,
        detail={"documento_id": document.id, "arquivo": document.original_filename, "sha256": sha256},
    )
    session.commit()
    session.refresh(document)
    return _doc_out(document)


@router.get("/personnel-assignments/{assignment_id}/documents/{doc_id}/download")
def download_assignment_document(
    project_id: int,
    assignment_id: int,
    doc_id: int,
    inline: bool = False,
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
    return file_response(path, doc.original_filename, doc.content_type, inline=inline)


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


# ------------------------------------------------- importar da planilha


async def _parse_personnel_upload(file: UploadFile) -> PersonnelSheetResult:
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Envie a planilha de acompanhamento (.xlsx).")
    content, _digest = await read_upload_limited(file)
    try:
        return parse_personnel_sheet(content)
    except BudgetImportError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _personnel_positions(session: Session, project_id: int) -> dict[int, BudgetPosition]:
    return {
        p.item_number: p
        for p in session.exec(
            select(BudgetPosition).where(BudgetPosition.project_id == project_id, BudgetPosition.category == "equipe_executora")
        ).all()
    }


def _existing_keys(session: Session, project_id: int) -> set[tuple[str, int, date]]:
    people = {p.id: p.full_name.casefold() for p in session.exec(select(Person).where(Person.project_id == project_id)).all()}
    return {
        (people.get(a.person_id, ""), a.budget_position_id, a.start_date)
        for a in session.exec(select(PersonnelAssignment).where(PersonnelAssignment.project_id == project_id)).all()
    }


@router.post("/personnel-import/preview", response_model=PersonnelImportPreviewOut)
async def preview_personnel_import(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Lê a aba "Equipe Executora" e mostra quem seria cadastrado em cada
    vaga, com o realizado da planilha ao lado do calculado pelo módulo —
    não grava nada."""
    result = await _parse_personnel_upload(file)
    positions = _personnel_positions(session, project_id)
    existing = _existing_keys(session, project_id)
    today = date.today()
    rows: list[PersonnelImportRowOut] = []
    for a in result.assignments:
        position = positions.get(a.item_number)
        accrual = compute_accrual(
            start_date=a.start_date, end_date=a.end_date, status=a.status, monthly_rate=a.monthly_rate, today=today
        )
        rows.append(PersonnelImportRowOut(
            item_number=a.item_number, role_title=a.role_title, person_name=a.person_name, status=a.status,
            start_date=a.start_date, end_date=a.end_date, monthly_rate=a.monthly_rate, sheet_value=a.sheet_value,
            accrued_value=accrual.accrued_value, sheet_row=a.sheet_row,
            position_found=position is not None,
            already_imported=position is not None
            and (a.person_name.casefold(), position.id, a.start_date) in existing,
        ))
    return PersonnelImportPreviewOut(
        rows=rows,
        warnings=result.warnings,
        sheet_total=sum((r.sheet_value or Decimal("0") for r in rows), Decimal("0")),
        accrued_total=sum((r.accrued_value for r in rows), Decimal("0")),
    )


@router.post("/personnel-import", response_model=PersonnelImportResultOut, status_code=status.HTTP_201_CREATED)
async def import_personnel(
    project_id: int,
    file: UploadFile = File(...),
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Cadastra as pessoas e as atribuições da aba "Equipe Executora".
    Idempotente: a mesma pessoa, na mesma vaga, com o mesmo início, não é
    cadastrada de novo. Vaga que não existe no orçamento fica de fora (com
    aviso) — importe o orçamento antes."""
    result = await _parse_personnel_upload(file)
    positions = _personnel_positions(session, project_id)
    existing = _existing_keys(session, project_id)
    people = {p.full_name.casefold(): p for p in session.exec(select(Person).where(Person.project_id == project_id)).all()}
    warnings = list(result.warnings)
    people_created = assignments_created = skipped = 0

    for a in result.assignments:
        position = positions.get(a.item_number)
        if position is None:
            warnings.append(
                f"Linha {a.sheet_row}: vaga {a.item_number} ({a.person_name}) não existe na Equipe Executora do "
                "orçamento — importe o orçamento antes."
            )
            skipped += 1
            continue
        key = (a.person_name.casefold(), position.id, a.start_date)
        if key in existing:
            skipped += 1
            continue
        person = people.get(a.person_name.casefold())
        if person is None:
            person = Person(project_id=project_id, full_name=a.person_name)
            session.add(person)
            session.flush()
            people[a.person_name.casefold()] = person
            people_created += 1
        assignment = PersonnelAssignment(
            project_id=project_id, person_id=person.id, budget_position_id=position.id, role_title=a.role_title,
            monthly_rate=a.monthly_rate, start_date=a.start_date, end_date=a.end_date, status=a.status,
            created_by_user_id=identity.user_id,
        )
        session.add(assignment)
        session.flush()
        record_event(
            session,
            project_id=project_id,
            entity_type="personnel_assignment",
            entity_id=assignment.id,
            action="importado_da_planilha",
            actor=identity,
            detail={"linha": a.sheet_row, "vaga": a.item_number, "situacao": a.status},
        )
        existing.add(key)
        assignments_created += 1
    session.commit()
    return PersonnelImportResultOut(
        people_created=people_created, assignments_created=assignments_created, skipped=skipped, warnings=warnings,
    )
