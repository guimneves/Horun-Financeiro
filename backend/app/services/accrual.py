"""Cálculo de acúmulo mensal de uma atribuição de pessoal (Equipe
Executora) — NUNCA armazenado, sempre recalculado a partir de
`start_date`/`end_date`/`monthly_rate`, mesma disciplina de
`services/balance.py`.

Convenção de mês parcial: dias corridos sobre base de 30 (mesma usada nos
recibos de bolsa/ajuda de custo do laboratório), não os dias reais do
calendário — evita que um mês de 31 dias "valha menos por dia" que um de
28.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between(start: date, end: date) -> Decimal:
    """Meses inteiros (convenção de aniversário, como cálculo de idade)
    mais a fração de dias/30 do mês parcial restante."""
    if end <= start:
        return Decimal("0")

    months = (end.year - start.year) * 12 + (end.month - start.month)
    anniversary = _add_months(start, months)
    if anniversary > end:
        months -= 1
        anniversary = _add_months(start, months)

    partial_days = (end - anniversary).days
    fraction = Decimal(partial_days) / Decimal(30)
    return (Decimal(months) + fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class AssignmentAccrual:
    accrued_months: Decimal
    accrued_value: Decimal
    committed_future_months: Decimal
    committed_future_value: Decimal


def compute_accrual(
    *,
    start_date: date,
    end_date: date | None,
    status: str,
    monthly_rate: Decimal,
    today: date,
) -> AssignmentAccrual:
    # Realizado: do início até o fim (se encerrada) ou até hoje (se ainda
    # ativa) — é trabalho que já aconteceu.
    effective_end = end_date if status == "encerrado" else today
    accrued_months = months_between(start_date, effective_end)
    accrued_value = (accrued_months * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Comprometido: só existe se a atribuição ainda está ativa E tem uma
    # data de fim futura já combinada (nomeação por prazo certo) — uma
    # atribuição ativa sem fim definido não compromete nada além de hoje.
    committed_months = Decimal("0")
    if status == "ativo" and end_date is not None and end_date > today:
        committed_months = months_between(today, end_date)
    committed_value = (committed_months * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return AssignmentAccrual(
        accrued_months=accrued_months,
        accrued_value=accrued_value,
        committed_future_months=committed_months,
        committed_future_value=committed_value,
    )
