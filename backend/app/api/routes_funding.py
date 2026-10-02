"""Quadro resumo do projeto (grupos, total, parcelas e % utilizado) e
histórico de eventos."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador
from app.db.models.audit import AuditEvent
from app.db.models.funding import FundingInstallment
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.schemas.funding import (
    AuditEventOut,
    GroupTotalOut,
    InstallmentOut,
    InstallmentsReplace,
    OverviewOut,
)
from app.services.audit import record_event
from app.services.balance import category_summary, item_balances
from app.services.funding import installments_with_utilization

router = APIRouter(prefix="/projects/{project_id}", tags=["funding"])

GROUP_LABELS = {"capital": "Despesas de Capital", "corrente": "Despesas Correntes"}


def _installments(session: Session, project_id: int) -> list[FundingInstallment]:
    return list(
        session.exec(select(FundingInstallment).where(FundingInstallment.project_id == project_id))
    )


def _total_executed(session: Session, project: Project) -> Decimal:
    if project.active_revision_id is None:
        return Decimal("0")
    return sum(
        (row.executed for row in category_summary(session, project.active_revision_id)), Decimal("0")
    )


@router.get("/installments", response_model=list[InstallmentOut])
def list_installments(
    project_id: int,
    session: Session = Depends(get_session),
    # valores em R$: só coordenador (core/redaction.py)
    _membership: ProjectMembership = Depends(require_coordenador),
):
    project = session.get(Project, project_id)
    return installments_with_utilization(_installments(session, project_id), _total_executed(session, project))


@router.put("/installments", response_model=list[InstallmentOut])
def replace_installments(
    project_id: int,
    body: InstallmentsReplace,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    previous = _installments(session, project_id)
    for inst in previous:
        session.delete(inst)
    session.flush()
    for number, item in enumerate(body.installments, start=1):
        session.add(
            FundingInstallment(
                project_id=project_id,
                number=number,
                amount=item.amount,
                expected_date=item.expected_date,
                note=item.note,
            )
        )
    record_event(
        session,
        project_id=project_id,
        entity_type="installments",
        entity_id=None,
        action="parcelas_substituidas",
        actor=identity,
        detail={
            "antes": [str(i.amount) for i in sorted(previous, key=lambda i: i.number)],
            "depois": [str(i.amount) for i in body.installments],
        },
    )
    session.commit()
    project = session.get(Project, project_id)
    return installments_with_utilization(_installments(session, project_id), _total_executed(session, project))


@router.get("/overview", response_model=OverviewOut)
def get_overview(
    project_id: int,
    session: Session = Depends(get_session),
    # valores em R$: só coordenador (core/redaction.py)
    _membership: ProjectMembership = Depends(require_coordenador),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")

    zero = Decimal("0")
    by_group: dict[str, dict[str, Decimal]] = {
        g: {"planned_value": zero, "yield_amount": zero, "committed": zero, "executed": zero, "balance": zero}
        for g in GROUP_LABELS
    }
    items_over_budget = 0
    if project.active_revision_id is not None:
        for row in category_summary(session, project.active_revision_id):
            totals = by_group[row.group]
            for field in totals:
                totals[field] += getattr(row, field)
        items_over_budget = sum(1 for r in item_balances(session, project.active_revision_id) if r.balance < 0)

    groups = [GroupTotalOut(group=g, label=GROUP_LABELS[g], **values) for g, values in by_group.items()]
    total = GroupTotalOut(
        group="total",
        label="Total do projeto",
        **{f: sum((getattr(g, f) for g in groups), zero) for f in by_group["capital"]},
    )
    return OverviewOut(
        groups=groups,
        total=total,
        total_executed=total.executed,
        installments=installments_with_utilization(_installments(session, project_id), total.executed),
        items_over_budget=items_over_budget,
    )


@router.get("/events", response_model=list[AuditEventOut])
def list_events(
    project_id: int,
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 200,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    query = select(AuditEvent).where(AuditEvent.project_id == project_id)
    if entity_type is not None:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditEvent.entity_id == entity_id)
    query = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(min(limit, 1000))  # type: ignore[attr-defined]
    events = list(session.exec(query))
    if membership.role == "coordenador":
        return events
    # O detalhe do evento traz valores (valor estimado/final, campos
    # editados) — quem não é coordenador vê só quem fez o quê e quando.
    return [AuditEventOut.model_validate(e, from_attributes=True).model_copy(update={"detail": "{}"}) for e in events]
