"""Painel da aba Resumo (ver services/dashboard.py). Todo membro do projeto
vê; valores em R$ só o coordenador (core/redaction.py) — o colaborador vê o
mesmo painel em percentuais."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.permissions import get_membership
from app.core.redaction import money
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.services.dashboard import GROUP_LABELS, Totals, _share, build_dashboard

router = APIRouter(prefix="/projects/{project_id}", tags=["dashboard"])


class TotalsOut(BaseModel):
    planned_value: Decimal | None
    yield_amount: Decimal | None
    committed: Decimal | None
    executed: Decimal | None
    balance: Decimal | None
    executed_share: Decimal | None  # fração do previsto + rendimentos
    committed_share: Decimal | None
    balance_share: Decimal | None
    overrun_share: Decimal | None


class GroupOut(TotalsOut):
    group: str
    label: str


class CategoryOut(TotalsOut):
    category: str
    label: str
    group: str
    items: int


class InstallmentOut(BaseModel):
    number: int
    amount: Decimal | None
    expected_date: date | None
    cumulative_amount: Decimal | None
    utilization: Decimal | None


class AlertOut(BaseModel):
    kind: str
    severity: str
    message: str
    category: str | None
    item_number: int | None
    process_id: int | None
    amount: Decimal | None


class PacePointOut(BaseModel):
    month: date
    # acumulados até o fim do mês, em fração do orçamento + rendimentos
    # (sempre) e em R$ (só coordenador); realizado nulo nos meses futuros
    personnel_share: Decimal | None
    purchases_share: Decimal | None
    expected_share: Decimal | None  # ritmo linear do prazo
    received_share: Decimal | None  # parcelas previstas até o mês
    executed: Decimal | None
    expected: Decimal | None
    received: Decimal | None


class PaceOut(BaseModel):
    points: list[PacePointOut]
    estimated_share: Decimal | None  # parte do realizado com data estimada pelo nº de processo
    estimated_amount: Decimal | None
    estimated_processes: int


class DashboardOut(BaseModel):
    values_visible: bool  # falso para colaborador: só percentuais
    total: TotalsOut
    groups: list[GroupOut]
    categories: list[CategoryOut]
    installments: list[InstallmentOut]
    time_elapsed_share: Decimal | None  # fração do prazo do projeto já decorrida
    alerts: list[AlertOut]
    pace: PaceOut


def _totals(t: Totals, visible: bool) -> dict:
    return {
        "planned_value": money(t.available - t.yield_amount, visible=visible),
        "yield_amount": money(t.yield_amount, visible=visible),
        "committed": money(t.committed, visible=visible),
        "executed": money(t.executed, visible=visible),
        "balance": money(t.balance, visible=visible),
        **t.shares(),
    }


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    project_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    visible = membership.role == "coordenador"
    board = build_dashboard(session, project)
    available = board.total.available
    return DashboardOut(
        values_visible=visible,
        total=TotalsOut(**_totals(board.total, visible)),
        groups=[GroupOut(group=g, label=GROUP_LABELS[g], **_totals(t, visible)) for g, t in board.groups.items()],
        categories=[
            CategoryOut(category=c.category, label=c.label, group=c.group, items=c.items, **_totals(c.totals, visible))
            for c in board.categories
        ],
        installments=[
            InstallmentOut(
                number=i.number,
                amount=money(i.amount, visible=visible),
                expected_date=i.expected_date,
                cumulative_amount=money(i.cumulative_amount, visible=visible),
                utilization=i.utilization,
            )
            for i in board.installments
        ],
        time_elapsed_share=board.time_elapsed_share,
        alerts=[
            AlertOut(
                kind=a.kind, severity=a.severity, message=a.message, category=a.category,
                item_number=a.item_number, process_id=a.process_id, amount=money(a.amount, visible=visible),
            )
            for a in board.alerts
        ],
        pace=PaceOut(
            points=[
                PacePointOut(
                    month=p.month,
                    personnel_share=None if p.personnel is None else _share(p.personnel, available),
                    purchases_share=None if p.purchases is None else _share(p.purchases, available),
                    expected_share=None if p.expected is None else _share(p.expected, available),
                    received_share=_share(p.received, available),
                    executed=money(p.executed, visible=visible),
                    expected=money(p.expected, visible=visible),
                    received=money(p.received, visible=visible),
                )
                for p in board.pace.points
            ],
            estimated_share=_share(board.pace.estimated_amount, available),
            estimated_amount=money(board.pace.estimated_amount, visible=visible),
            estimated_processes=board.pace.estimated_processes,
        ),
    )
