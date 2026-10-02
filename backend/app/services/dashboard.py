"""Painel da aba Resumo (pedido do usuário: "parecido com a planilha, com
gráficos") — tudo calculado aqui, a partir das mesmas regras de saldo de
`services/balance.py` e das parcelas de `services/funding.py`:

- indicadores do projeto (orçamento + rendimentos, realizado, comprometido,
  saldo) e o % do prazo já decorrido, para comparar com o % executado;
- por categoria: o Quadro Resumo da planilha, com os percentuais de cada
  parte (realizado / comprometido / saldo / estouro) do previsto;
- parcelas recebidas × usadas;
- alertas: itens com saldo negativo, itens acima de 90% do previsto,
  compras paradas antes da autorização e processos sem valor lançado.

Percentuais sempre (o colaborador vê o painel só em %); valores em R$ só
para o coordenador — a rota aplica `core/redaction.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.db.models.budget import EXPENSE_CATEGORIES
from app.db.models.funding import FundingInstallment
from app.db.models.project import Project
from app.db.models.purchase import PRE_AUTHORIZATION_STATES, PurchaseProcess
from app.services.balance import category_summary, item_balances
from app.services.funding import installments_with_utilization

ZERO = Decimal("0")
NEAR_LIMIT = Decimal("0.90")  # item "quase no fim": 90% do previsto já usado
STALLED_DAYS = 30  # compra parada na mesma etapa antes da autorização

GROUP_LABELS = {"capital": "Despesas de Capital", "corrente": "Despesas Correntes"}


def _share(part: Decimal, whole: Decimal) -> Decimal | None:
    """Fração (0..1+) de `whole`; nula quando não há previsto."""
    if whole <= 0:
        return None
    return (part / whole).quantize(Decimal("0.0001"))


@dataclass
class Totals:
    planned_value: Decimal = ZERO
    yield_amount: Decimal = ZERO
    committed: Decimal = ZERO
    executed: Decimal = ZERO
    balance: Decimal = ZERO

    @property
    def available(self) -> Decimal:
        return self.planned_value + self.yield_amount

    def add(self, other: "Totals") -> None:
        for name in ("planned_value", "yield_amount", "committed", "executed", "balance"):
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def shares(self) -> dict[str, Decimal | None]:
        total = self.available
        overrun = -self.balance if self.balance < 0 else ZERO
        return {
            "executed_share": _share(self.executed, total),
            "committed_share": _share(self.committed, total),
            "balance_share": _share(max(self.balance, ZERO), total),
            "overrun_share": _share(overrun, total),
        }


@dataclass
class CategoryRow:
    category: str
    label: str
    group: str
    totals: Totals
    items: int


@dataclass
class Alert:
    kind: str  # saldo_negativo | quase_no_fim | compra_parada | sem_valor
    severity: str  # danger | warning | info
    message: str
    category: str | None = None
    item_number: int | None = None
    process_id: int | None = None
    amount: Decimal | None = None  # em R$ (oculto para colaborador)


@dataclass
class Dashboard:
    total: Totals
    groups: dict[str, Totals]
    categories: list[CategoryRow]
    installments: list
    time_elapsed_share: Decimal | None
    alerts: list[Alert] = field(default_factory=list)


def _time_elapsed(project: Project, today: date) -> Decimal | None:
    if project.start_date is None or project.end_date is None or project.end_date <= project.start_date:
        return None
    elapsed = (min(max(today, project.start_date), project.end_date) - project.start_date).days
    return (Decimal(elapsed) / Decimal((project.end_date - project.start_date).days)).quantize(Decimal("0.0001"))


def build_dashboard(session: Session, project: Project, *, today: date | None = None) -> Dashboard:
    today = today or date.today()
    rows: list[CategoryRow] = []
    groups = {g: Totals() for g in GROUP_LABELS}
    total = Totals()
    alerts: list[Alert] = []

    if project.active_revision_id is not None:
        balances = item_balances(session, project.active_revision_id)
        counts: dict[str, int] = {}
        for item in balances:
            counts[item.category] = counts.get(item.category, 0) + 1
        for summary in category_summary(session, project.active_revision_id):
            if not counts.get(summary.category):
                continue  # categoria sem nenhum item no orçamento
            totals = Totals(
                planned_value=summary.planned_value, yield_amount=summary.yield_amount,
                committed=summary.committed, executed=summary.executed, balance=summary.balance,
            )
            rows.append(CategoryRow(summary.category, summary.label, summary.group, totals, counts[summary.category]))
            groups[summary.group].add(totals)
            total.add(totals)

        for item in sorted(balances, key=lambda i: (i.balance, i.category, i.item_number)):
            label = EXPENSE_CATEGORIES[item.category]["label"]
            available = item.planned_value + item.yield_amount
            used = item.committed + item.executed
            if item.balance < 0:
                alerts.append(Alert(
                    kind="saldo_negativo", severity="danger", category=item.category, item_number=item.item_number,
                    amount=item.balance,
                    message=f"Item {item.item_number} ({label}) com saldo negativo",
                ))
            elif available > 0 and used / available >= NEAR_LIMIT:
                alerts.append(Alert(
                    kind="quase_no_fim", severity="warning", category=item.category, item_number=item.item_number,
                    amount=item.balance,
                    message=(
                        f"Item {item.item_number} ({label}) com {int(used / available * 100)}% do previsto usado"
                    ),
                ))

    processes = session.exec(select(PurchaseProcess).where(PurchaseProcess.project_id == project.id)).all()
    limit = datetime.now(timezone.utc) - timedelta(days=STALLED_DAYS)
    for p in processes:
        updated = p.updated_at if p.updated_at.tzinfo else p.updated_at.replace(tzinfo=timezone.utc)
        if p.status in PRE_AUTHORIZATION_STATES and updated < limit:
            days = (datetime.now(timezone.utc) - updated).days
            alerts.append(Alert(
                kind="compra_parada", severity="warning", process_id=p.id, amount=p.estimated_value,
                message=f"Compra \"{p.title}\" parada na mesma etapa há {days} dias",
            ))
        if p.status != "cancelado" and p.estimated_value == 0 and not p.final_value:
            alerts.append(Alert(
                kind="sem_valor", severity="info", process_id=p.id,
                message=f"Processo {p.process_number or p.title} sem valor lançado (entrou com R$ 0)",
            ))

    installments = installments_with_utilization(
        list(session.exec(select(FundingInstallment).where(FundingInstallment.project_id == project.id))),
        total.executed,
    )
    return Dashboard(
        total=total,
        groups=groups,
        categories=rows,
        installments=installments,
        time_elapsed_share=_time_elapsed(project, today),
        alerts=alerts,
    )
