"""Painel da aba Resumo: indicadores, Quadro Resumo por categoria com as
partes em %, parcelas e alertas. Colaborador vê só percentuais."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.db.models.project import Project
from app.services.dashboard import _time_elapsed
from tests.conftest import ADMIN, COLAB
from tests.test_drive import LEDGER, _project_with_budget, drive  # noqa: F401 — fixture


def _board(client, project_id, headers=ADMIN):
    r = client.get(f"/projects/{project_id}/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_dashboard_matches_the_category_summary(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    board = _board(client, project["id"])
    cats = {c["category"]: c for c in board["categories"]}
    # só as categorias com item no orçamento aparecem
    assert set(cats) == {"material_consumo_nacional", "equip_nacional"}

    consumo = cats["material_consumo_nacional"]
    assert Decimal(consumo["executed"]) == Decimal("1500.50")
    assert Decimal(consumo["executed_share"]) == Decimal("0.3001")  # 1.500,50 de 5.000
    assert Decimal(consumo["overrun_share"]) == 0

    equip = cats["equip_nacional"]  # 7.000 realizado sobre 5.000 previstos
    assert Decimal(equip["balance"]) == Decimal("-2000.00")
    assert Decimal(equip["overrun_share"]) == Decimal("0.4000") and Decimal(equip["balance_share"]) == 0

    total = board["total"]
    assert Decimal(total["executed"]) == Decimal("8500.50")
    assert Decimal(total["planned_value"]) == Decimal("10000")
    assert {g["group"] for g in board["groups"]} == {"capital", "corrente"}


def test_alerts_point_to_what_needs_action(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json={}, headers=ADMIN)  # sem planilha: valores zero
    alerts = _board(client, project["id"])["alerts"]
    kinds = {a["kind"] for a in alerts}
    assert "sem_valor" in kinds  # processos que entraram com R$ 0


def test_negative_balance_alert(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    negative = [a for a in _board(client, project["id"])["alerts"] if a["kind"] == "saldo_negativo"]
    assert len(negative) == 1 and negative[0]["category"] == "equip_nacional"
    assert Decimal(negative[0]["amount"]) == Decimal("-2000.00")


def test_collaborator_sees_percentages_but_no_money(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    board = _board(client, project["id"], headers=COLAB)
    assert board["values_visible"] is False
    consumo = next(c for c in board["categories"] if c["category"] == "material_consumo_nacional")
    assert consumo["executed"] is None and consumo["planned_value"] is None
    assert Decimal(consumo["executed_share"]) == Decimal("0.3001")
    assert all(a["amount"] is None for a in board["alerts"])


def test_time_elapsed_share():
    project = Project(code="x", name="x", start_date=date(2024, 1, 1), end_date=date(2025, 1, 1))
    assert _time_elapsed(project, date(2024, 7, 2)) == Decimal("0.5000")
    assert _time_elapsed(project, date(2023, 1, 1)) == 0
    assert _time_elapsed(project, date(2030, 1, 1)) == 1
    assert _time_elapsed(Project(code="y", name="y"), date(2024, 7, 2)) is None


# --- ritmo de execução -------------------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from app.db.models.personnel import PersonnelAssignment  # noqa: E402
from app.db.models.purchase import PurchaseProcess  # noqa: E402
from app.services.pace import build_pace, estimate_date_from_number  # noqa: E402


def _process(number, value, status="autorizado", realized_on=None):
    return PurchaseProcess(
        project_id=1, budget_position_id=1, process_number=number, title="x", quantity=Decimal("1"),
        estimated_unit_value=value, estimated_value=value, status=status, realized_on=realized_on,
        created_by_user_id="u", created_by_username="u", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_process_number_gives_an_approximate_date():
    assert estimate_date_from_number("2025-1") == date(2025, 1, 1)
    assert estimate_date_from_number("2025-6900").month in (6, 7)  # meio da numeração do ano
    assert estimate_date_from_number("2025-99999") == date(2025, 12, 31)  # nunca passa do ano
    assert estimate_date_from_number("sem número") is None and estimate_date_from_number(None) is None


def test_pace_accumulates_month_by_month():
    project = Project(code="x", name="x", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
    processes = [
        _process("2025-1", Decimal("1000"), realized_on=date(2025, 2, 10)),  # data exata
        _process("2025-1", Decimal("500")),  # estimada pelo número: janeiro
        _process("2025-2", Decimal("9999"), status="cotacao"),  # comprometido: fora do realizado
    ]
    person = PersonnelAssignment(
        project_id=1, person_id=1, budget_position_id=1, role_title="x", monthly_rate=Decimal("100"),
        start_date=date(2025, 2, 15), end_date=date(2025, 3, 31), status="encerrado", created_by_user_id="u",
    )
    pace = build_pace(project, processes, [person], [], Decimal("12000"), date(2025, 4, 20))
    by_month = {p.month: p for p in pace.points}
    assert [p.month.month for p in pace.points] == list(range(1, 13))  # toda a vigência
    assert by_month[date(2025, 1, 1)].executed == Decimal("500")
    assert by_month[date(2025, 2, 1)].executed == Decimal("1600")  # +1.000 compra +100 pessoal
    assert by_month[date(2025, 4, 1)].executed == Decimal("1700")  # dois meses de pessoal ao todo
    assert by_month[date(2025, 5, 1)].executed is None  # futuro
    assert by_month[date(2025, 12, 1)].expected == Decimal("12000.00")  # ritmo do prazo chega a 100%
    assert pace.estimated_amount == Decimal("500") and pace.estimated_processes == 1


def test_dashboard_has_pace_in_shares(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.patch(f"/projects/{project['id']}", json={"start_date": "2024-01-01", "end_date": "2027-12-31"}, headers=ADMIN)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    pace = _board(client, project["id"], headers=COLAB)["pace"]
    assert pace["points"] and pace["points"][0]["month"] == "2024-01-01"
    assert all(p["executed"] is None for p in pace["points"])  # colaborador: sem R$
    last = [p for p in pace["points"] if p["purchases_share"] is not None][-1]
    total = _board(client, project["id"])["total"]
    together = Decimal(last["purchases_share"]) + Decimal(last["personnel_share"])
    assert abs(together - Decimal(total["executed_share"])) <= Decimal("0.0002")  # só arredondamento
