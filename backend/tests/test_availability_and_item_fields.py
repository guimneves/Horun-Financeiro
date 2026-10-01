from __future__ import annotations

from tests.conftest import ADMIN, COLAB


def _project_with_budget(client, unit_value="1000", planned_quantity="10", coppetec_process_number=None):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={
            "category": "equip_nacional", "item_number": 1, "description": "X",
            "unit_value": unit_value, "planned_quantity": planned_quantity,
            "coppetec_process_number": coppetec_process_number,
        },
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    return project, item


def test_item_stores_and_returns_coppetec_process_number(client):
    project, item = _project_with_budget(client, coppetec_process_number="2024-1234")
    assert item["coppetec_process_number"] == "2024-1234"

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert balance[0]["coppetec_process_number"] == "2024-1234"


def test_check_availability_true_when_fits(client):
    project, item = _project_with_budget(client, unit_value="1000", planned_quantity="10")  # planejado 10000
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/check-availability",
        json={"budget_position_id": item["position_id"], "quantity": "5", "estimated_unit_value": "1000"},
        headers=COLAB,
    )
    assert resp.status_code == 200
    assert resp.json() == {"available": True}
    assert set(resp.json().keys()) == {"available"}  # nunca vaza o saldo real


def test_check_availability_false_when_exceeds(client):
    project, item = _project_with_budget(client, unit_value="1000", planned_quantity="10")  # planejado 10000
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/check-availability",
        json={"budget_position_id": item["position_id"], "quantity": "20", "estimated_unit_value": "1000"},
        headers=COLAB,
    )
    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_check_availability_accounts_for_committed_purchases(client):
    project, item = _project_with_budget(client, unit_value="1000", planned_quantity="10")  # planejado 10000
    client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "X", "quantity": "8", "estimated_unit_value": "1000"},
        headers=ADMIN,
    )  # comprometido 8000, sobra 2000

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/check-availability",
        json={"budget_position_id": item["position_id"], "quantity": "3", "estimated_unit_value": "1000"},
        headers=COLAB,
    )
    assert resp.json() == {"available": False}  # 3000 > 2000 restantes
