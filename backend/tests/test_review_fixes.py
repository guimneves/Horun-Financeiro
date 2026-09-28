"""Regressão pros 10 achados confirmados na revisão de código (ver commit
"Correções da revisão de código" / PR) — cada teste aqui existe pra travar
um bug específico que já foi real."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from tests.conftest import ADMIN, COLAB


def _project_with_budget(client, category="equip_nacional", unit_value="1000", planned_quantity="10"):
    project = client.post("/projects", json={"code": "25.465", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={
            "category": category, "item_number": 1, "description": "Item",
            "unit_value": unit_value, "planned_quantity": planned_quantity,
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


def _create_process(client, project, item, estimated_unit_value="500", quantity="2"):
    return client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={
            "budget_position_id": item["position_id"], "title": "Compra",
            "quantity": quantity, "estimated_unit_value": estimated_unit_value,
        },
        headers=ADMIN,
    ).json()


def _upload(client, project_id, process_id, doc_type):
    return client.post(
        f"/projects/{project_id}/purchase-processes/{process_id}/documents",
        data={"doc_type": doc_type},
        files={"file": (f"{doc_type}.pdf", b"conteudo", "application/pdf")},
        headers=ADMIN,
    )


def _transition(client, project_id, process_id, action, headers=ADMIN, **extra):
    return client.post(
        f"/projects/{project_id}/purchase-processes/{process_id}/transition",
        json={"action": action, **extra},
        headers=headers,
    )


# 1. remove_member não deixa remover o último coordenador
def test_cannot_remove_last_coordenador(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    members = client.get(f"/projects/{project['id']}/members", headers=ADMIN).json()
    admin_membership = next(m for m in members if m["user_id"] == "u-admin")

    resp = client.delete(f"/projects/{project['id']}/members/{admin_membership['id']}", headers=ADMIN)
    assert resp.status_code == 409


def test_can_remove_coordenador_when_another_remains(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "coordenador"},
        headers=ADMIN,
    )
    members = client.get(f"/projects/{project['id']}/members", headers=ADMIN).json()
    admin_membership = next(m for m in members if m["user_id"] == "u-admin")

    resp = client.delete(f"/projects/{project['id']}/members/{admin_membership['id']}", headers=ADMIN)
    assert resp.status_code == 204


# 2. cancelar exige coordenador depois de autorizado
def test_colaborador_can_cancel_before_authorization(client):
    project, item = _project_with_budget(client)
    process = _create_process(client, project, item)
    resp = _transition(client, project["id"], process["id"], "cancelar", headers=COLAB, reason="desisti")
    assert resp.status_code == 200


def test_colaborador_cannot_cancel_after_authorization(client):
    project, item = _project_with_budget(client)
    process = _create_process(client, project, item)
    _upload(client, project["id"], process["id"], "cotacao")
    _transition(client, project["id"], process["id"], "avancar_cotacao")
    _transition(client, project["id"], process["id"], "solicitar_autorizacao")
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao")
    _transition(client, project["id"], process["id"], "autorizar", vendor="Fornecedor X")

    resp = _transition(client, project["id"], process["id"], "cancelar", headers=COLAB, reason="tentando")
    assert resp.status_code == 409

    resp = _transition(client, project["id"], process["id"], "cancelar", headers=ADMIN, reason="coordenador cancelou")
    assert resp.status_code == 200


# 3. update_process (PATCH) exige coordenador depois de autorizado
def test_colaborador_can_edit_process_before_authorization(client):
    project, item = _project_with_budget(client)
    process = _create_process(client, project, item)
    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{process['id']}", json={"vendor": "X"}, headers=COLAB
    )
    assert resp.status_code == 200


def test_colaborador_cannot_edit_process_after_authorization(client):
    project, item = _project_with_budget(client)
    process = _create_process(client, project, item)
    _upload(client, project["id"], process["id"], "cotacao")
    _transition(client, project["id"], process["id"], "avancar_cotacao")
    _transition(client, project["id"], process["id"], "solicitar_autorizacao")
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao")
    _transition(client, project["id"], process["id"], "autorizar", vendor="Fornecedor X")

    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{process['id']}",
        json={"estimated_unit_value": "9999"},
        headers=COLAB,
    )
    assert resp.status_code == 403

    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{process['id']}",
        json={"estimated_unit_value": "9999"},
        headers=ADMIN,
    )
    assert resp.status_code == 200


# 4. update_assignment bloqueado depois de encerrado
def test_cannot_edit_closed_assignment(client):
    project, item = _project_with_budget(client, category="equipe_executora")
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "X", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()
    client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/close",
        json={"end_date": "2024-03-01"},
        headers=ADMIN,
    )
    resp = client.patch(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}",
        json={"monthly_rate": "5000"},
        headers=ADMIN,
    )
    assert resp.status_code == 409


# 5. close_assignment rejeita data de fim no futuro
def test_close_assignment_rejects_future_end_date(client):
    project, item = _project_with_budget(client, category="equipe_executora")
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "X", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()
    future = (date.today() + timedelta(days=30)).isoformat()
    resp = client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/close",
        json={"end_date": future},
        headers=ADMIN,
    )
    assert resp.status_code == 422


# 6. activate_revision só a partir de rascunho
def test_cannot_reactivate_superseded_revision(client):
    project, item = _project_with_budget(client)
    revisions = client.get(f"/projects/{project['id']}/revisions", headers=ADMIN).json()
    old_revision_id = revisions[0]["id"]

    new_revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{new_revision['id']}/activate", headers=ADMIN)

    resp = client.post(f"/projects/{project['id']}/revisions/{old_revision_id}/activate", headers=ADMIN)
    assert resp.status_code == 409


# 7. documento de pessoal retido depois de encerrado
def test_cannot_delete_receipt_after_assignment_closed(client):
    project, item = _project_with_budget(client, category="equipe_executora")
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "X", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()
    upload = client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents",
        files={"file": ("recibo.pdf", b"conteudo", "application/pdf")},
        headers=ADMIN,
    )
    doc_id = upload.json()["id"]
    client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/close",
        json={"end_date": "2024-03-01"},
        headers=ADMIN,
    )
    resp = client.delete(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents/{doc_id}", headers=ADMIN
    )
    assert resp.status_code == 409


# 8. autorizar não aceita mais estimated_value do cliente
def test_transition_request_ignores_estimated_value_override(client):
    project, item = _project_with_budget(client)
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="2")
    _upload(client, project["id"], process["id"], "cotacao")
    _transition(client, project["id"], process["id"], "avancar_cotacao")
    _transition(client, project["id"], process["id"], "solicitar_autorizacao")
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao")

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "autorizar", "vendor": "X", "estimated_value": "999999"},
        headers=ADMIN,
    )
    assert resp.status_code == 200
    # campo desconhecido é só ignorado pelo schema — valor continua o real
    assert Decimal(resp.json()["estimated_value"]) == Decimal("1000.00")


# 9. save_upload separa purchases/personnel por owner_kind
def test_purchase_and_personnel_documents_use_separate_storage_namespaces(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    purchase_item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1000", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    personnel_item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equipe_executora", "item_number": 1, "description": "Y", "unit_value": "1", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    process = _create_process(client, project, purchase_item)
    doc = _upload(client, project["id"], process["id"], "cotacao").json()

    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": personnel_item["position_id"],
            "role_title": "X", "monthly_rate": "1", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()
    receipt = client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents",
        files={"file": ("r.pdf", b"x", "application/pdf")},
        headers=ADMIN,
    ).json()

    # baixa os dois e confirma que ambos existem (prova que os caminhos não colidiram)
    assert client.get(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{doc['id']}/download", headers=ADMIN
    ).status_code == 200
    assert client.get(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents/{receipt['id']}/download",
        headers=ADMIN,
    ).status_code == 200


# 10. item_balances não faz N+1 (checagem indireta: resultado continua correto com múltiplos itens)
def test_balance_correct_across_multiple_items_after_batching(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    item1 = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1000", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    item2 = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "material_consumo_nacional", "item_number": 1, "description": "Y", "unit_value": "500", "planned_quantity": "2"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)

    _create_process(client, project, item1, estimated_unit_value="1000", quantity="1")
    _create_process(client, project, item2, estimated_unit_value="500", quantity="2")

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    by_position = {b["position_id"]: b for b in balance}
    assert Decimal(by_position[item1["position_id"]]["committed"]) == Decimal("1000.00")
    assert Decimal(by_position[item2["position_id"]]["committed"]) == Decimal("1000.00")
