"""Parcelas de repasse e % utilizado — mesma regra da linha "% Utilizado" do
Quadro Resumo da planilha:

  1ª parcela: realizado ÷ valor da 1ª (no máximo 100%);
  parcela N: só aparece quando o realizado já cobriu o acumulado até a
  parcela anterior ("-" na planilha); então é realizado ÷ acumulado até N.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.db.models.funding import FundingInstallment
from app.schemas.funding import InstallmentOut


def installments_with_utilization(
    installments: list[FundingInstallment], total_executed: Decimal
) -> list[InstallmentOut]:
    result: list[InstallmentOut] = []
    cumulative = Decimal("0")
    previous_cumulative = Decimal("0")
    for index, inst in enumerate(sorted(installments, key=lambda i: i.number)):
        previous_cumulative = cumulative
        cumulative += inst.amount
        utilization: Decimal | None
        if cumulative <= 0 or (index > 0 and total_executed < previous_cumulative):
            utilization = None
        else:
            utilization = min(total_executed / cumulative, Decimal("1")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        result.append(
            InstallmentOut(
                number=inst.number,
                amount=inst.amount,
                expected_date=inst.expected_date,
                note=inst.note,
                cumulative_amount=cumulative,
                utilization=utilization,
            )
        )
    return result
