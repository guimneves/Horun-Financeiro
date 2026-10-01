"""Validação de dinheiro/quantidade na entrada (app/core/money.py) e PATCH
com null explícito — antes, quantidade negativa liberava saldo e null
derrubava a rota com 500."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import ADMIN, COLAB
from tests.test_purchases import _create_process, _project_with_active_budget


def _post_process(client, project, item, quantity, unit, headers=ADMIN):
    return client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={
            "budget_position_id": item["position_id"], "title": "Reagente",
            "quantity": quantity, "estimated_unit_value": unit,
        },
        headers=headers,
    )


@pytest.mark.parametrize(
    ("quantity", "unit"),
    [("-1", "500"), ("0", "500"), ("2", "-500"), ("1.005", "10"), ("1", "10.001"), ("1", "1e20")],
)
def test_process_rejects_invalid_quantity_or_value(client, quantity, unit):
    project, item = _project_with_active_budget(client)
    assert _post_process(client, project, item, quantity, unit).status_code == 422


def test_negative_quantity_cannot_free_balance_for_a_collaborator(client):
    # Orçamento de 10.000; o primeiro processo ocupa tudo. Antes, um segundo
    # processo com quantidade negativa baixava o "comprometido" e abria saldo.
    project, item = _project_with_active_budget(client)
    _create_process(client, project, item, estimated_unit_value="1000", quantity="10")
    resp = _post_process(client, project, item, "-5", "1000", headers=COLAB)
    assert resp.status_code == 422
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["balance"]) == Decimal("0")


def test_estimated_value_is_rounded_to_cents(client):
    project, item = _project_with_active_budget(client)
    process = _post_process(client, project, item, "1.25", "1.25").json()
    # 1,25 × 1,25 = 1,5625 → R$ 1,56 (o mesmo que o banco guarda)
    assert Decimal(process["estimated_value"]) == Decimal("1.56")


@pytest.mark.parametrize("field", ["quantity", "estimated_unit_value", "title"])
def test_patch_process_with_explicit_null_is_422_not_500(client, field):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{process['id']}", json={field: None}, headers=ADMIN
    )
    assert resp.status_code == 422


def test_patch_process_can_still_clear_vendor(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    url = f"/projects/{project['id']}/purchase-processes/{process['id']}"
    client.patch(url, json={"vendor": "Fornecedor X"}, headers=ADMIN)
    resp = client.patch(url, json={"vendor": None}, headers=ADMIN)
    assert resp.status_code == 200 and resp.json()["vendor"] is None


def _draft_item(client):
    project = client.post("/projects", json={"code": "25.466", "name": "Projeto B"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    base = f"/projects/{project['id']}/revisions/{revision['id']}/items"
    return base, project, revision


@pytest.mark.parametrize(("unit", "qty"), [("-1", "1"), ("1", "-1"), ("1.234", "1")])
def test_budget_item_rejects_negative_or_sub_cent_values(client, unit, qty):
    base, _, _ = _draft_item(client)
    resp = client.post(
        base,
        json={"category": "equip_nacional", "item_number": 1, "description": "Item", "unit_value": unit, "planned_quantity": qty},
        headers=ADMIN,
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("field", ["unit_value", "planned_quantity", "description"])
def test_patch_budget_item_with_explicit_null_is_422_not_500(client, field):
    base, _, _ = _draft_item(client)
    item = client.post(
        base,
        json={"category": "equip_nacional", "item_number": 1, "description": "Item", "unit_value": "10", "planned_quantity": "3"},
        headers=ADMIN,
    ).json()
    assert client.patch(f"{base}/{item['id']}", json={field: None}, headers=ADMIN).status_code == 422


def test_budget_item_planned_value_is_rounded_to_cents(client):
    base, _, _ = _draft_item(client)
    item = client.post(
        base,
        json={"category": "equip_nacional", "item_number": 1, "description": "Item", "unit_value": "0.15", "planned_quantity": "0.15"},
        headers=ADMIN,
    ).json()
    # 0,15 × 0,15 = 0,0225 → R$ 0,02
    assert Decimal(item["planned_value"]) == Decimal("0.02")


def test_validation_error_is_one_portuguese_sentence(client):
    # O frontend mostra `detail` direto (api/client.ts) — tem que ser texto.
    project, item = _project_with_active_budget(client)
    resp = _post_process(client, project, item, "-1", "10.001")
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert "Quantidade: tem que ser maior que zero." in detail
    assert "Valor unitário: aceita no máximo 2 casas decimais." in detail

    process = _create_process(client, project, item)
    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{process['id']}", json={"title": None}, headers=ADMIN
    )
    assert resp.json()["detail"] == "Título: não pode ser vazio."
