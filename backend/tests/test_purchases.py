from __future__ import annotations

from decimal import Decimal

from tests.conftest import ADMIN, COLAB


def _project_with_active_budget(client, category="equip_nacional", unit_value="1000", planned_quantity="10"):
    project = client.post("/projects", json={"code": "25.465", "name": "Maturação Artificial"}, headers=ADMIN).json()
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


def _create_process(client, project, item, estimated_unit_value="500", quantity="2", headers=ADMIN):
    return client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={
            "budget_position_id": item["position_id"], "title": "Computador novo",
            "quantity": quantity, "estimated_unit_value": estimated_unit_value,
        },
        headers=headers,
    ).json()


def _upload(client, project_id, process_id, doc_type, filename="doc.pdf", headers=ADMIN):
    return client.post(
        f"/projects/{project_id}/purchase-processes/{process_id}/documents",
        data={"doc_type": doc_type},
        files={"file": (filename, b"conteudo fake", "application/pdf")},
        headers=headers,
    )


def test_creating_process_reserves_balance_as_committed(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="2")
    assert process["status"] == "verificacao_orcamento"
    assert Decimal(process["estimated_value"]) == Decimal("1000.00")

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["committed"]) == Decimal("1000.00")
    assert Decimal(balance[0]["balance"]) == Decimal("10000.00") - Decimal("1000.00")


def test_equipe_executora_rejected_from_purchase_flow(client):
    project, item = _project_with_active_budget(client, category="equipe_executora")
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "X", "quantity": "1", "estimated_unit_value": "1"},
        headers=ADMIN,
    )
    assert resp.status_code == 422


def test_transition_blocked_without_required_document(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "avancar_cotacao"},
        headers=ADMIN,
    )
    assert resp.status_code == 409


def test_max_three_quotes_enforced(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    for i in range(3):
        resp = _upload(client, project["id"], process["id"], "cotacao", filename=f"cotacao{i}.pdf")
        assert resp.status_code == 201
    resp = _upload(client, project["id"], process["id"], "cotacao", filename="cotacao4.pdf")
    assert resp.status_code == 409


def test_only_coordenador_can_authorize(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    _upload(client, project["id"], process["id"], "cotacao")
    client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "avancar_cotacao"},
        headers=ADMIN,
    )
    client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "solicitar_autorizacao"},
        headers=ADMIN,
    )
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao")

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "autorizar"},
        headers=COLAB,
    )
    assert resp.status_code == 409  # TransitionError (papel incorreto) também vira 409, mesmo com o documento presente

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "autorizar", "vendor": "Fornecedor X"},
        headers=ADMIN,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "autorizado"
    assert resp.json()["vendor"] == "Fornecedor X"


def test_full_lifecycle_moves_committed_to_executed(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="2")
    pid = process["id"]

    _upload(client, project["id"], pid, "cotacao")
    _transition(client, project["id"], pid, "avancar_cotacao")
    _transition(client, project["id"], pid, "solicitar_autorizacao")
    _upload(client, project["id"], pid, "solicitacao_autorizacao")
    _transition(client, project["id"], pid, "autorizar", vendor="Fornecedor X")

    _upload(client, project["id"], pid, "nota_fiscal")
    _transition(client, project["id"], pid, "emitir_nota_fiscal", final_value="980")

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    # ainda não concluído — final_value só vira "realizado" depois de concluído
    assert Decimal(balance[0]["committed"]) == Decimal("1000.00")
    assert Decimal(balance[0]["executed"]) == 0

    _upload(client, project["id"], pid, "comprovante_recebimento")
    _transition(client, project["id"], pid, "confirmar_recebimento")
    result = _transition(client, project["id"], pid, "concluir")
    assert result["status"] == "concluido"

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["committed"]) == 0
    assert Decimal(balance[0]["executed"]) == Decimal("980.00")
    assert Decimal(balance[0]["balance"]) == Decimal("10000.00") - Decimal("980.00")


def _transition(client, project_id, process_id, action, **extra):
    resp = client.post(
        f"/projects/{project_id}/purchase-processes/{process_id}/transition",
        json={"action": action, **extra},
        headers=ADMIN,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_cancel_requires_reason_and_frees_committed_balance(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="2")

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "cancelar"},
        headers=ADMIN,
    )
    assert resp.status_code == 409  # sem motivo

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "cancelar", "reason": "Fornecedor desistiu"},
        headers=ADMIN,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelado"

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["committed"]) == 0


def test_new_attempt_can_reference_cancelled_but_not_concluded(client):
    project, item = _project_with_active_budget(client)
    cancelled = _create_process(client, project, item)
    client.post(
        f"/projects/{project['id']}/purchase-processes/{cancelled['id']}/transition",
        json={"action": "cancelar", "reason": "Preço subiu"},
        headers=ADMIN,
    )

    retry = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={
            "budget_position_id": item["position_id"], "title": "Computador novo (2ª tentativa)",
            "quantity": "2", "estimated_unit_value": "500", "previous_attempt_id": cancelled["id"],
        },
        headers=ADMIN,
    )
    assert retry.status_code == 201
    assert retry.json()["previous_attempt_id"] == cancelled["id"]


def test_documents_retained_after_completion_cannot_be_deleted(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    upload = _upload(client, project["id"], process["id"], "cotacao")
    doc_id = upload.json()["id"]

    client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "cancelar", "reason": "teste"},
        headers=ADMIN,
    )

    resp = client.delete(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{doc_id}", headers=ADMIN
    )
    assert resp.status_code == 409
