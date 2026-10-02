"""Ritmo de execução (aba Resumo): realizado acumulado mês a mês, comparado
com o ritmo linear do prazo (gastar por igual do início ao fim da vigência)
e com o que já foi repassado em parcelas.

Mesmos valores de `services/balance.py` — o último ponto bate com o
realizado do projeto. O que muda é QUANDO cada valor entra:

- Equipe Executora: exato, mês a mês, pela mesma conta de
  `services/accrual.py` (meses de calendário, do início até o fim ou hoje).
- Compras: na data em que ficaram realizadas (`realized_on`, gravada ao
  autorizar pelo módulo ou informada à mão). Processos importados do drive
  não têm essa data — nem a pasta tem (as datas dos arquivos são as da cópia
  para o OneDrive). Para esses, a data é ESTIMADA pelo nº de processo
  COPPETEC: o ano é o do número e, dentro do ano, a numeração é sequencial e
  quase linear no tempo (ver COPPETEC_NUMBERS_PER_YEAR). O painel mostra
  quanto do realizado está com data estimada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.db.models.personnel import PersonnelAssignment
from app.db.models.project import Project
from app.db.models.purchase import REALIZED_STATES, PurchaseProcess

ZERO = Decimal("0")

# Quantos nº de processo a COPPETEC emite por ano, aproximadamente — medido
# nos processos reais de um projeto cujos arquivos traziam a data no nome
# (nº ~12.600 em dezembro, ~8.500 em agosto, ~5.400 em maio). Erro típico da
# estimativa: um mês, o que basta para o gráfico mensal.
COPPETEC_NUMBERS_PER_YEAR = 13800

_NUMBER_RE = re.compile(r"^(\d{4})-(\d+)$")


def _month(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def estimate_date_from_number(process_number: str | None) -> date | None:
    """Data aproximada de um nº de processo COPPETEC normalizado ("AAAA-N")."""
    match = _NUMBER_RE.match(process_number or "")
    if match is None:
        return None
    year, number = int(match.group(1)), int(match.group(2))
    if not 2000 <= year <= 2100:
        return None
    day = min(int(number / COPPETEC_NUMBERS_PER_YEAR * 365), 364)
    return date(year, 1, 1) + timedelta(days=day)


def process_date(process: PurchaseProcess) -> tuple[date, bool]:
    """(data em que o processo ficou realizado, se a data é estimada)."""
    if process.realized_on is not None:
        return process.realized_on, False
    estimated = estimate_date_from_number(process.process_number)
    if estimated is not None:
        return estimated, True
    # sem data nem nº: a criação é o melhor que há (processos manuais antigos)
    return process.created_at.date(), True


def _process_value(process: PurchaseProcess) -> Decimal:
    return process.final_value if process.final_value is not None else process.estimated_value


@dataclass
class PacePoint:
    month: date  # primeiro dia do mês
    personnel: Decimal | None  # acumulado até o fim do mês; None nos meses futuros
    purchases: Decimal | None
    expected: Decimal | None  # ritmo linear do prazo; None sem vigência
    received: Decimal  # parcelas previstas até o fim do mês, acumuladas

    @property
    def executed(self) -> Decimal | None:
        if self.personnel is None or self.purchases is None:
            return None
        return self.personnel + self.purchases


@dataclass
class Pace:
    points: list[PacePoint] = field(default_factory=list)
    estimated_amount: Decimal = ZERO  # parte do realizado com data estimada
    estimated_processes: int = 0


def build_pace(
    project: Project,
    processes: list[PurchaseProcess],
    assignments: list[PersonnelAssignment],
    installments: list,
    available: Decimal,
    today: date,
) -> Pace:
    pace = Pace()
    monthly: dict[date, list[Decimal]] = {}  # mês -> [pessoal, compras]

    def add(month: date, index: int, value: Decimal) -> None:
        monthly.setdefault(month, [ZERO, ZERO])[index] += value

    for a in assignments:
        # mesma regra de compute_accrual: até o fim (encerrada) ou até hoje
        end = (a.end_date or today) if a.status == "encerrado" else today
        month, last = _month(a.start_date), _month(end)
        while month <= last:
            add(month, 0, a.monthly_rate)
            month = _next_month(month)

    for p in processes:
        if p.status not in REALIZED_STATES:
            continue
        when, estimated = process_date(p)
        value = _process_value(p)
        add(_month(min(when, today)), 1, value)
        if estimated:
            pace.estimated_amount += value
            pace.estimated_processes += 1

    # gasto anterior ao início da vigência também aparece, no mês em que houve
    starts = list(monthly) + ([_month(project.start_date)] if project.start_date else [])
    if not starts:
        return pace
    has_term = project.start_date is not None and project.end_date is not None and project.end_date > project.start_date
    first = min(starts)
    last = _month(max(project.end_date, today) if has_term else today)

    received_by_month = sorted(
        (_month(i.expected_date), i.amount) for i in installments if i.expected_date is not None
    )
    personnel = purchases = received = ZERO
    month = first
    while month <= last:
        month_end = _next_month(month) - timedelta(days=1)
        future = month > _month(today)
        personnel += monthly.get(month, [ZERO, ZERO])[0]
        purchases += monthly.get(month, [ZERO, ZERO])[1]
        received = sum((amount for m, amount in received_by_month if m <= month), ZERO)
        expected = None
        if has_term:
            span = (project.end_date - project.start_date).days
            elapsed = (min(max(month_end, project.start_date), project.end_date) - project.start_date).days
            expected = (available * elapsed / span).quantize(Decimal("0.01"))
        pace.points.append(PacePoint(
            month=month,
            personnel=None if future else personnel,
            purchases=None if future else purchases,
            expected=expected,
            received=received,
        ))
        month = _next_month(month)
    return pace
