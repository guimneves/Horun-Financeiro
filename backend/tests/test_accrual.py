from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.accrual import compute_accrual, months_between


def test_months_between_whole_months():
    assert months_between(date(2024, 5, 1), date(2024, 8, 1)) == Decimal("3.00")


def test_months_between_partial_month_uses_30_day_basis():
    # 15 dias depois do "aniversário" de 1 mês = 1 + 15/30 = 1.5
    assert months_between(date(2024, 5, 1), date(2024, 6, 16)) == Decimal("1.50")


def test_months_between_clamps_short_month_anniversary():
    # 31/jan -> fev só tem 29 dias em 2024 (bissexto): "aniversário" de 1 mês
    # vira 29/fev (clamp), então 31/jan -> 1/mar é 1 mês completo + 1 dia
    # (de 29/fev a 1/mar) = 1 + 1/30
    assert months_between(date(2024, 1, 31), date(2024, 3, 1)) == Decimal("1.03")


def test_accrual_active_open_ended_has_no_committed_future():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=None, status="ativo",
        monthly_rate=Decimal("1000"), today=date(2024, 4, 1),
    )
    assert result.accrued_months == Decimal("3.00")
    assert result.accrued_value == Decimal("3000.00")
    assert result.committed_future_value == Decimal("0")


def test_accrual_active_with_future_end_date_has_committed_future():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=date(2024, 7, 1), status="ativo",
        monthly_rate=Decimal("1000"), today=date(2024, 4, 1),
    )
    assert result.accrued_value == Decimal("3000.00")  # jan->abr, ja trabalhado
    assert result.committed_future_value == Decimal("3000.00")  # abr->jul, ainda por vir


def test_accrual_closed_assignment_uses_end_date_not_today():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=date(2024, 3, 1), status="encerrado",
        monthly_rate=Decimal("1000"), today=date(2026, 1, 1),
    )
    assert result.accrued_value == Decimal("2000.00")
    assert result.committed_future_value == Decimal("0")
