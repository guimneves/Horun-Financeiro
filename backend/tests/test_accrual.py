from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.accrual import compute_accrual, paid_months


def test_paid_months_counts_calendar_months_inclusive():
    # jun, jul, ago, set -> a planilha também conta o mês final
    assert paid_months(date(2024, 5, 1), date(2024, 8, 1)) == Decimal("4.00")


def test_paid_months_matches_spreadsheet_example():
    # Equipe Executora: início 01/05/2024, hoje 01/10/2026 -> Período = 30
    assert paid_months(date(2024, 5, 1), date(2026, 10, 1)) == Decimal("30.00")


def test_paid_months_ignores_day_of_month():
    assert paid_months(date(2024, 5, 31), date(2024, 6, 1)) == Decimal("2.00")
    assert paid_months(date(2024, 5, 1), date(2024, 5, 31)) == Decimal("1.00")


def test_paid_months_is_zero_before_start():
    assert paid_months(date(2024, 5, 1), date(2024, 4, 30)) == Decimal("0.00")


def test_accrual_active_open_ended_has_no_committed_future():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=None, status="ativo",
        monthly_rate=Decimal("1000"), today=date(2024, 4, 1),
    )
    assert result.accrued_months == Decimal("4.00")
    assert result.accrued_value == Decimal("4000.00")
    assert result.committed_future_value == Decimal("0")


def test_accrual_active_with_future_end_date_has_committed_future():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=date(2024, 7, 1), status="ativo",
        monthly_rate=Decimal("1000"), today=date(2024, 4, 1),
    )
    assert result.accrued_value == Decimal("4000.00")  # jan-abr, já contado
    assert result.committed_future_value == Decimal("3000.00")  # mai-jul, ainda por vir


def test_accrual_closed_assignment_uses_end_date_not_today():
    result = compute_accrual(
        start_date=date(2024, 1, 1), end_date=date(2024, 3, 1), status="encerrado",
        monthly_rate=Decimal("1000"), today=date(2026, 1, 1),
    )
    assert result.accrued_value == Decimal("3000.00")  # jan, fev, mar
    assert result.committed_future_value == Decimal("0")


def test_accrual_closed_one_year_matches_spreadsheet_row():
    # Planilha, linha de uma atribuição encerrada: 01/10/2024 a 01/10/2025 -> 13 meses
    result = compute_accrual(
        start_date=date(2024, 10, 1), end_date=date(2025, 10, 1), status="encerrado",
        monthly_rate=Decimal("1000"), today=date(2026, 10, 1),
    )
    assert result.accrued_months == Decimal("13.00")
