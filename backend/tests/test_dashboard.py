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
