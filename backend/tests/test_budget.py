from __future__ import annotations

from decimal import Decimal

from tests.conftest import ADMIN, COLAB


def _project(client):
    return client.post("/projects", json={"code": "25.465", "name": "Maturação Artificial"}, headers=ADMIN).json()


def _revision(client, project_id, label="Baseline SIGITEC"):
    return client.post(
        f"/projects/{project_id}/revisions",
        json={"label": label, "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()


def test_budget_item_planned_value_computed_server_side(client):
    project = _project(client)
    revision = _revision(client, project["id"])
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={
            "category": "equip_nacional", "item_number": 1, "description": "Computador",
            "justification": "Acesso remoto", "unit_value": "5499", "planned_quantity": "6",
        },
        headers=ADMIN,
    ).json()
    assert Decimal(item["planned_value"]) == Decimal("32994.00")


def test_balance_reflects_planned_value_and_yield_until_purchases_exist(client):
    project = _project(client)
    revision = _revision(client, project["id"])
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={
            "category": "equip_nacional", "item_number": 1, "description": "Computador",
            "unit_value": "5499", "planned_quantity": "6",
        },
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["balance"]) == Decimal("32994.00")
    assert Decimal(balance[0]["committed"]) == 0
    assert Decimal(balance[0]["executed"]) == 0

    client.patch(
        f"/projects/{project['id']}/positions/{item['position_id']}/yield",
        json={"yield_amount": "100"},
        headers=ADMIN,
    )
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["balance"]) == Decimal("33094.00")


def test_colaborador_can_read_balance_but_not_create_items(client):
    project = _project(client)
    revision = _revision(client, project["id"])
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    read = client.get(f"/projects/{project['id']}/balance", headers=COLAB)
    assert read.status_code == 200

    write = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1", "planned_quantity": "1"},
        headers=COLAB,
    )
    assert write.status_code == 403


def test_editing_items_blocked_outside_draft_revision(client):
    project = _project(client)
    revision = _revision(client, project["id"])
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "Computador", "unit_value": "100", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    resp = client.patch(
        f"/projects/{project['id']}/revisions/{revision['id']}/items/{item['id']}",
        json={"unit_value": "200"},
        headers=ADMIN,
    )
    assert resp.status_code == 409


def test_new_revision_clones_items_from_active_revision(client):
    project = _project(client)
    revision_1 = _revision(client, project["id"], label="Baseline SIGITEC")
    client.post(
        f"/projects/{project['id']}/revisions/{revision_1['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "Computador", "unit_value": "5499", "planned_quantity": "6"},
        headers=ADMIN,
    )
    client.post(f"/projects/{project['id']}/revisions/{revision_1['id']}/activate", headers=ADMIN)

    revision_2 = _revision(client, project["id"], label="Reformulação Nº1")
    assert revision_2["revision_number"] == 1

    cloned_items = client.get(
        f"/projects/{project['id']}/revisions/{revision_2['id']}/items", headers=ADMIN
    ).json()
    assert len(cloned_items) == 1
    assert cloned_items[0]["description"] == "Computador"
    assert Decimal(cloned_items[0]["planned_value"]) == Decimal("32994.00")

    # revisão antiga continua intacta e consultável — histórico preservado
    old_items = client.get(
        f"/projects/{project['id']}/revisions/{revision_1['id']}/items", headers=ADMIN
    ).json()
    assert len(old_items) == 1


def test_category_summary_groups_by_category(client):
    project = _project(client)
    revision = _revision(client, project["id"])
    client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "Computador", "unit_value": "1000", "planned_quantity": "2"},
        headers=ADMIN,
    )
    client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "material_consumo_nacional", "item_number": 1, "description": "Gás", "unit_value": "500", "planned_quantity": "1"},
        headers=ADMIN,
    )
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    summary = client.get(f"/projects/{project['id']}/summary", headers=ADMIN).json()
    by_category = {s["category"]: s for s in summary}
    assert Decimal(by_category["equip_nacional"]["planned_value"]) == Decimal("2000.00")
    assert Decimal(by_category["material_consumo_nacional"]["planned_value"]) == Decimal("500.00")
    # categorias sem nenhum item aparecem zeradas, não somem — Quadro Resumo mostra a lista inteira
    assert Decimal(by_category["passagens"]["planned_value"]) == 0
