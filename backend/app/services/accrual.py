"""Cálculo de acúmulo mensal de uma atribuição de pessoal (Equipe
Executora) — NUNCA armazenado, sempre recalculado a partir de
`start_date`/`end_date`/`monthly_rate`, mesma disciplina de
`services/balance.py`.

Convenção da planilha de acompanhamento de saldo (aba "Equipe Executora"):
conta MESES DE CALENDÁRIO, ignorando o dia, e o mês de referência final
entra na conta (o pagamento é feito no mês seguinte ao trabalhado). Na
planilha: `Período = (ano(Fim+1 mês) − ano(Início))×12 + mês(Fim+1 mês) −
mês(Início)`, ou seja, de 01/05/2024 até 01/10/2026 são 30 meses
(maio/2024 a outubro/2026, inclusive). Não existe mês fracionado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def paid_months(start: date, end: date) -> Decimal:
    """Meses de calendário de `start` a `end`, ambos inclusive (só ano e mês
    contam). Zero se `end` for anterior ao mês de `start`."""
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    return Decimal(max(months, 0)).quantize(Decimal("0.01"))


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
    # ativa) — mesma regra da planilha, que usa TODAY() para quem está ativo.
    effective_end = (end_date or today) if status == "encerrado" else today
    accrued_months = paid_months(start_date, effective_end)
    accrued_value = (accrued_months * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Comprometido: só existe se a atribuição ainda está ativa E tem uma
    # data de fim futura já combinada (nomeação por prazo certo) — uma
    # atribuição ativa sem fim definido não compromete nada além de hoje.
    # (Extensão do programa: a planilha não projeta meses futuros.)
    committed_months = Decimal("0")
    if status == "ativo" and end_date is not None and end_date > today:
        committed_months = max(paid_months(start_date, end_date) - accrued_months, Decimal("0"))
    committed_value = (committed_months * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return AssignmentAccrual(
        accrued_months=accrued_months,
        accrued_value=accrued_value,
        committed_future_months=committed_months,
        committed_future_value=committed_value,
    )
