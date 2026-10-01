"""Orçamento: revisões (reformulações), itens dentro de uma revisão, saldo
por item ("Saldo por Item") e resumo por categoria ("Quadro Resumo").

Uma revisão nova (`POST .../revisions`) clona os itens da revisão ativa —
histórico de cada reformulação passada fica intacto em `BudgetItem`s
antigos, nunca sobrescritos. Editar itens só é permitido em revisões
`rascunho`; `activate` publica e substitui a anterior.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.money import round_money
from app.core.permissions import get_membership, require_coordenador
from app.db.models.budget import EXPENSE_CATEGORIES, BudgetItem, BudgetPosition, BudgetRevision
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.schemas.budget import (
    BudgetItemCreate,
    BudgetItemOut,
    BudgetItemUpdate,
    CategorySummaryOut,
    ItemBalanceOut,
    RevisionCreate,
    RevisionOut,
    YieldUpdate,
)
from app.services.balance import category_summary, item_balances

router = APIRouter(prefix="/projects/{project_id}", tags=["budget"])


def _item_out(item: BudgetItem, position: BudgetPosition) -> BudgetItemOut:
    return BudgetItemOut(
        id=item.id,
        revision_id=item.revision_id,
        position_id=item.position_id,
        category=position.category,
        item_number=position.item_number,
        description=item.description,
        justification=item.justification,
        unit_value=item.unit_value,
        planned_quantity=item.planned_quantity,
        planned_value=item.planned_value,
        yield_amount=item.yield_amount,
        note=item.note,
    )


def _get_revision(session: Session, project_id: int, revision_id: int) -> BudgetRevision:
    revision = session.get(BudgetRevision, revision_id)
    if revision is None or revision.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revisão não encontrada.")
    return revision


@router.get("/revisions", response_model=list[RevisionOut])
def list_revisions(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    revisions = session.exec(
        select(BudgetRevision)
        .where(BudgetRevision.project_id == project_id)
        .order_by(BudgetRevision.revision_number)
    ).all()
    return revisions


@router.post("/revisions", response_model=RevisionOut, status_code=status.HTTP_201_CREATED)
def create_revision(
    project_id: int,
    body: RevisionCreate,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(require_coordenador),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")

    last = session.exec(
        select(BudgetRevision)
        .where(BudgetRevision.project_id == project_id)
        .order_by(BudgetRevision.revision_number.desc())
    ).first()
    next_number = 0 if last is None else last.revision_number + 1

    revision = BudgetRevision(
        project_id=project_id,
        revision_number=next_number,
        label=body.label,
        status="rascunho",
        effective_date=body.effective_date,
        note=body.note,
        created_by_user_id=membership.user_id,
        created_by_username=membership.username,
    )
    session.add(revision)
    session.commit()
    session.refresh(revision)

    # Clona os itens da revisão ativa (se houver) pra revisão nova — ponto
    # de partida editável, sem repetir "adicionar item por adicionar item"
    # numa reformulação que normalmente só ajusta valores existentes.
    if project.active_revision_id is not None:
        source_items = session.exec(
            select(BudgetItem).where(BudgetItem.revision_id == project.active_revision_id)
        ).all()
        for source in source_items:
            clone = BudgetItem(
                revision_id=revision.id,
                position_id=source.position_id,
                description=source.description,
                justification=source.justification,
                unit_value=source.unit_value,
                planned_quantity=source.planned_quantity,
                planned_value=source.planned_value,
                yield_amount=source.yield_amount,
                note=source.note,
            )
            session.add(clone)
        session.commit()

    return revision


@router.get("/revisions/{revision_id}", response_model=RevisionOut)
def get_revision(
    project_id: int,
    revision_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    return _get_revision(session, project_id, revision_id)


@router.post("/revisions/{revision_id}/activate", response_model=RevisionOut)
def activate_revision(
    project_id: int,
    revision_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    project = session.get(Project, project_id)
    revision = _get_revision(session, project_id, revision_id)
    if revision.status != "rascunho":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível ativar uma revisão em rascunho.")

    if project.active_revision_id is not None and project.active_revision_id != revision.id:
        previous = session.get(BudgetRevision, project.active_revision_id)
        if previous is not None:
            previous.status = "substituida"
            session.add(previous)

    revision.status = "ativa"
    project.active_revision_id = revision.id
    session.add(revision)
    session.add(project)
    session.commit()
    session.refresh(revision)
    return revision


@router.get("/revisions/{revision_id}/items", response_model=list[BudgetItemOut])
def list_items(
    project_id: int,
    revision_id: int,
    category: str | None = None,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    _get_revision(session, project_id, revision_id)
    query = (
        select(BudgetItem, BudgetPosition)
        .join(BudgetPosition, BudgetPosition.id == BudgetItem.position_id)
        .where(BudgetItem.revision_id == revision_id)
    )
    if category is not None:
        query = query.where(BudgetPosition.category == category)
    return [_item_out(item, position) for item, position in session.exec(query)]


@router.post("/revisions/{revision_id}/items", response_model=BudgetItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    project_id: int,
    revision_id: int,
    body: BudgetItemCreate,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    revision = _get_revision(session, project_id, revision_id)
    if revision.status != "rascunho":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível editar itens numa revisão em rascunho.")
    if body.category not in EXPENSE_CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Categoria inválida.")

    position = session.exec(
        select(BudgetPosition).where(
            BudgetPosition.project_id == project_id,
            BudgetPosition.category == body.category,
            BudgetPosition.item_number == body.item_number,
        )
    ).first()
    if position is None:
        position = BudgetPosition(project_id=project_id, category=body.category, item_number=body.item_number)
        session.add(position)
        session.commit()
        session.refresh(position)

    planned_value = round_money(body.unit_value * body.planned_quantity)
    item = BudgetItem(
        revision_id=revision_id,
        position_id=position.id,
        description=body.description,
        justification=body.justification,
        unit_value=body.unit_value,
        planned_quantity=body.planned_quantity,
        planned_value=planned_value,
        note=body.note,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_out(item, position)


@router.patch("/revisions/{revision_id}/items/{item_id}", response_model=BudgetItemOut)
def update_item(
    project_id: int,
    revision_id: int,
    item_id: int,
    body: BudgetItemUpdate,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    revision = _get_revision(session, project_id, revision_id)
    if revision.status != "rascunho":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível editar itens numa revisão em rascunho.")

    item = session.get(BudgetItem, item_id)
    if item is None or item.revision_id != revision_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item não encontrado.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.planned_value = round_money(item.unit_value * item.planned_quantity)
    session.add(item)
    session.commit()
    session.refresh(item)

    position = session.get(BudgetPosition, item.position_id)
    return _item_out(item, position)


@router.delete("/revisions/{revision_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    project_id: int,
    revision_id: int,
    item_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    revision = _get_revision(session, project_id, revision_id)
    if revision.status != "rascunho":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível editar itens numa revisão em rascunho.")

    item = session.get(BudgetItem, item_id)
    if item is None or item.revision_id != revision_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item não encontrado.")
    session.delete(item)
    session.commit()


@router.patch("/positions/{position_id}/yield", response_model=BudgetItemOut)
def update_yield(
    project_id: int,
    position_id: int,
    body: YieldUpdate,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    """Lança rendimento na revisão ATIVA sem precisar abrir uma revisão
    nova — rendimento é um lançamento periódico, não uma reformulação."""
    project = session.get(Project, project_id)
    if project is None or project.active_revision_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Projeto não tem revisão orçamentária ativa.")

    position = session.get(BudgetPosition, position_id)
    if position is None or position.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item de orçamento não encontrado.")

    item = session.exec(
        select(BudgetItem).where(
            BudgetItem.revision_id == project.active_revision_id,
            BudgetItem.position_id == position_id,
        )
    ).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item não encontrado na revisão ativa.")

    item.yield_amount = body.yield_amount
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_out(item, position)


def _require_active_revision(session: Session, project_id: int) -> BudgetRevision:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    if project.active_revision_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Projeto não tem revisão orçamentária ativa.")
    return session.get(BudgetRevision, project.active_revision_id)


@router.get("/balance", response_model=list[ItemBalanceOut])
def get_balance(
    project_id: int,
    category: str | None = None,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    revision = _require_active_revision(session, project_id)
    rows = item_balances(session, revision.id, category)
    return [ItemBalanceOut(**vars(r)) for r in rows]


@router.get("/summary", response_model=list[CategorySummaryOut])
def get_summary(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    revision = _require_active_revision(session, project_id)
    rows = category_summary(session, revision.id)
    return [CategorySummaryOut(**vars(r)) for r in rows]
