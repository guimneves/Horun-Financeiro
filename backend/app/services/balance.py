"""Cálculo de saldo por item e por categoria — fonte única de verdade,
usada tanto pela tabela "Saldo por Item" quanto pelo "Quadro Resumo".

saldo = planejado + rendimentos − comprometido − realizado

`comprometido` soma o valor estimado de processos de compra ainda em
andamento (não concluídos nem cancelados/rejeitados) — é isso que faz o
saldo já refletir uma compra em cotação/autorização antes mesmo dela virar
nota fiscal, resolvendo a dor original (colaborador não precisa perguntar
ao coordenador se "aquele valor já tá comprometido"). `realizado` soma o
valor final de processos concluídos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.db.models.budget import EXPENSE_CATEGORIES, BudgetItem, BudgetPosition
from app.db.models.personnel import PersonnelAssignment
from app.db.models.purchase import IN_PROGRESS_STATES, PurchaseProcess
from app.services.accrual import compute_accrual


@dataclass
class ItemBalance:
    position_id: int
    category: str
    item_number: int
    description: str
    justification: str
    unit_value: Decimal
    planned_quantity: Decimal
    planned_value: Decimal
    yield_amount: Decimal
    committed: Decimal
    executed: Decimal
    balance: Decimal


def _committed_and_executed_from(
    processes: list[PurchaseProcess], assignments: list[PersonnelAssignment], today: date
) -> tuple[Decimal, Decimal]:
    # Um BudgetPosition só recebe PurchaseProcess OU PersonnelAssignment,
    # nunca os dois (a rota de criação de cada um bloqueia a categoria
    # errada) — somar os dois sem checar a categoria aqui é seguro e evita
    # ter que buscar a posição só pra ramificar.
    committed = sum(
        (p.estimated_value for p in processes if p.status in IN_PROGRESS_STATES), Decimal("0")
    )
    executed = sum(
        (p.final_value for p in processes if p.status == "concluido" and p.final_value is not None),
        Decimal("0"),
    )

    for assignment in assignments:
        accrual = compute_accrual(
            start_date=assignment.start_date,
            end_date=assignment.end_date,
            status=assignment.status,
            monthly_rate=assignment.monthly_rate,
            today=today,
        )
        committed += accrual.committed_future_value
        executed += accrual.accrued_value

    return committed, executed


def item_balances(session: Session, revision_id: int, category: str | None = None) -> list[ItemBalance]:
    query = (
        select(BudgetItem, BudgetPosition)
        .where(BudgetItem.revision_id == revision_id)
        .join(BudgetPosition, BudgetPosition.id == BudgetItem.position_id)
    )
    if category is not None:
        query = query.where(BudgetPosition.category == category)

    rows = list(session.exec(query))
    position_ids = [position.id for _, position in rows]

    # Uma consulta pra cada tabela em vez de duas por item — evita N+1
    # quando a revisão tem dezenas/centenas de linhas (comum na planilha
    # real que este módulo substitui).
    processes_by_position: dict[int, list[PurchaseProcess]] = {}
    assignments_by_position: dict[int, list[PersonnelAssignment]] = {}
    if position_ids:
        for process in session.exec(
            select(PurchaseProcess).where(PurchaseProcess.budget_position_id.in_(position_ids))
        ):
            processes_by_position.setdefault(process.budget_position_id, []).append(process)
        for assignment in session.exec(
            select(PersonnelAssignment).where(PersonnelAssignment.budget_position_id.in_(position_ids))
        ):
            assignments_by_position.setdefault(assignment.budget_position_id, []).append(assignment)

    today = date.today()
    results: list[ItemBalance] = []
    for item, position in rows:
        committed, executed = _committed_and_executed_from(
            processes_by_position.get(position.id, []),
            assignments_by_position.get(position.id, []),
            today,
        )
        balance = item.planned_value + item.yield_amount - committed - executed
        results.append(
            ItemBalance(
                position_id=position.id,
                category=position.category,
                item_number=position.item_number,
                description=item.description,
                justification=item.justification,
                unit_value=item.unit_value,
                planned_quantity=item.planned_quantity,
                planned_value=item.planned_value,
                yield_amount=item.yield_amount,
                committed=committed,
                executed=executed,
                balance=balance,
            )
        )
    results.sort(key=lambda r: (r.category, r.item_number))
    return results


@dataclass
class CategorySummary:
    category: str
    label: str
    group: str
    planned_value: Decimal
    yield_amount: Decimal
    committed: Decimal
    executed: Decimal
    balance: Decimal


def category_summary(session: Session, revision_id: int) -> list[CategorySummary]:
    items = item_balances(session, revision_id)
    by_category: dict[str, list[ItemBalance]] = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    summaries: list[CategorySummary] = []
    for category, meta in EXPENSE_CATEGORIES.items():
        rows = by_category.get(category, [])
        planned = sum((r.planned_value for r in rows), Decimal("0"))
        yield_total = sum((r.yield_amount for r in rows), Decimal("0"))
        committed = sum((r.committed for r in rows), Decimal("0"))
        executed = sum((r.executed for r in rows), Decimal("0"))
        summaries.append(
            CategorySummary(
                category=category,
                label=str(meta["label"]),
                group=str(meta["group"]),
                planned_value=planned,
                yield_amount=yield_total,
                committed=committed,
                executed=executed,
                balance=planned + yield_total - committed - executed,
            )
        )
    return summaries
