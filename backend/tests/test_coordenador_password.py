"""Senha mestra de coordenador — login, elevação de sessão via header,
redação de valores monetários pra quem não é coordenador, e troca de
senha (única, compartilhada por todo o módulo)."""

from __future__ import annotations

from decimal import Decimal

from app.core.config import settings
from tests.conftest import ADMIN, COLAB

DEFAULT_PASSWORD = settings.default_coordenador_password


def _project_with_budget(client):
    project = client.post("/projects", json={"code": "25.465", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1000", "planned_quantity": "10"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    return project, item


def _login(client, password=DEFAULT_PASSWORD):
    return client.post("/auth/coordenador-session", json={"password": password})


def test_login_with_wrong_password_fails(client):
    resp = _login(client, "senha-errada")
    assert resp.status_code == 401


def test_login_with_default_password_succeeds(client):
    resp = _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["expires_at"] > 0


def test_colaborador_sees_null_values_without_token(client):
    project, _item = _project_with_budget(client)
    balance = client.get(f"/projects/{project['id']}/balance", headers=COLAB).json()
    assert balance[0]["balance"] is None
    assert balance[0]["planned_value"] is None
    assert isinstance(balance[0]["has_balance"], bool)


def test_colaborador_sees_real_values_with_valid_coordenador_token(client):
    project, _item = _project_with_budget(client)
    token = _login(client).json()["token"]
    headers = {**COLAB, "X-Horun-Coordenador-Token": token}

    balance = client.get(f"/projects/{project['id']}/balance", headers=headers).json()
    assert Decimal(balance[0]["balance"]) == Decimal("10000.00")


def test_token_also_elevates_role_for_coordenador_only_actions(client):
    project, _item = _project_with_budget(client)
    token = _login(client).json()["token"]
    headers = {**COLAB, "X-Horun-Coordenador-Token": token}

    # criar revisao normalmente exige coordenador — colaborador comum tomaria 403
    resp = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=headers,
    )
    assert resp.status_code == 201


def test_invalid_token_does_not_elevate(client):
    project, _item = _project_with_budget(client)
    headers = {**COLAB, "X-Horun-Coordenador-Token": "token-invalido"}
    resp = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_change_password_requires_valid_token(client):
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-123"},
    )
    assert resp.status_code == 401


def test_change_password_requires_correct_current_password(client):
    token = _login(client).json()["token"]
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": "senha-errada", "new_password": "nova-senha-123"},
        headers={"X-Horun-Coordenador-Token": token},
    )
    assert resp.status_code == 401


def test_change_password_then_old_password_stops_working(client):
    token = _login(client).json()["token"]
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-123"},
        headers={"X-Horun-Coordenador-Token": token},
    )
    assert resp.status_code == 204

    assert _login(client, DEFAULT_PASSWORD).status_code == 401
    assert _login(client, "nova-senha-123").status_code == 200


def test_purchase_process_values_redacted_for_colaborador(client):
    project, item = _project_with_budget(client)
    process = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "X", "quantity": "2", "estimated_unit_value": "500"},
        headers=ADMIN,
    ).json()
    assert Decimal(process["estimated_value"]) == Decimal("1000.00")  # criador (coordenador) ve normalmente

    as_colab = client.get(
        f"/projects/{project['id']}/purchase-processes/{process['id']}", headers=COLAB
    ).json()
    assert as_colab["estimated_value"] is None
    assert as_colab["estimated_unit_value"] is None
    assert as_colab["status"] == process["status"]  # dados operacionais continuam visiveis


def test_personnel_assignment_values_redacted_for_colaborador(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    personnel_item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equipe_executora", "item_number": 1, "description": "Y", "unit_value": "1000", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": personnel_item["position_id"],
            "role_title": "X", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    )

    assignments = client.get(f"/projects/{project['id']}/personnel-assignments", headers=COLAB).json()
    assert assignments[0]["monthly_rate"] is None
    assert assignments[0]["accrued_value"] is None
    assert assignments[0]["person_name"] == "X"  # dados nao-monetarios continuam visiveis
