"""Paridade com a planilha (quantidade disponível, parcelas, quadro resumo) e
flexibilidade (política de saldo por projeto, requisito de documento
dispensável com justificativa, histórico de eventos, nº de processo único,
limite de upload)."""

from __future__ import annotations

import re
from decimal import Decimal

from app.core.config import settings
from tests.conftest import ADMIN, COLAB
from tests.test_purchases import _create_process, _project_with_active_budget, _transition, _upload


def _authorize(client, project, process_id):
    _upload(client, project["id"], process_id, "cotacao")
    _transition(client, project["id"], process_id, "avancar_cotacao")
    _transition(client, project["id"], process_id, "solicitar_autorizacao")
    _upload(client, project["id"], process_id, "solicitacao_autorizacao")
    return _transition(client, project["id"], process_id, "autorizar", vendor="Fornecedor X")


# ---------- paridade ----------


def test_available_quantity_subtracts_quantity_in_committed_and_realized_processes(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="2")

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()[0]
    assert Decimal(balance["available_quantity"]) == Decimal("8.00")  # 10 previstas − 2 comprometidas

    _authorize(client, project, process["id"])
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()[0]
    assert Decimal(balance["available_quantity"]) == Decimal("8.00")  # realizada: continua descontada

    _transition(client, project["id"], process["id"], "cancelar", reason="Desistência")
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()[0]
    assert Decimal(balance["available_quantity"]) == Decimal("10.00")  # cancelado devolve


def test_available_quantity_is_null_for_personnel(client):
    project, _item = _project_with_active_budget(client, category="equipe_executora")
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()[0]
    assert balance["available_quantity"] is None


def test_lump_sum_item_has_no_available_quantity(client):
    # material de consumo com quantidade 1 = verba gasta em várias compras
    project, item = _project_with_active_budget(
        client, category="material_consumo_nacional", unit_value="5000", planned_quantity="1"
    )
    _create_process(client, project, item, estimated_unit_value="100", quantity="1")
    _create_process(client, project, item, estimated_unit_value="200", quantity="1")
    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()[0]
    assert balance["available_quantity"] is None  # e não 1 − 2 = −1
    assert Decimal(balance["balance"]) == Decimal("4700.00")


def test_installments_and_utilization_follow_the_spreadsheet_rule(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")
    url = f"/projects/{project['id']}/installments"

    assert client.put(url, json={"installments": [{"amount": "400"}, {"amount": "600"}]}, headers=COLAB).status_code == 403
    resp = client.put(
        url,
        json={"installments": [{"amount": "400", "expected_date": "2024-05-01"}, {"amount": "600"}, {"amount": "1000"}]},
        headers=ADMIN,
    )
    assert resp.status_code == 200
    # nada realizado ainda: a 1ª mostra 0%; as demais ficam "-" (nulas)
    parcelas = resp.json()
    assert [p["number"] for p in parcelas] == [1, 2, 3]
    assert [Decimal(p["cumulative_amount"]) for p in parcelas] == [400, 1000, 2000]
    assert Decimal(parcelas[0]["utilization"]) == 0 and parcelas[1]["utilization"] is None
    assert client.get(url, headers=COLAB).status_code == 403  # valores: só coordenador

    process = _create_process(client, project, item, estimated_unit_value="500", quantity="1")
    _authorize(client, project, process["id"])  # realizado = 500

    parcelas = client.get(url, headers=ADMIN).json()
    assert Decimal(parcelas[0]["utilization"]) == Decimal("1.0000")  # 500 ÷ 400, no máximo 100%
    assert Decimal(parcelas[1]["utilization"]) == Decimal("0.5000")  # 400 cobertos → 500 ÷ 1000
    assert parcelas[2]["utilization"] is None  # 1000 não foram cobertos ainda


def test_overview_matches_quadro_resumo_groups_and_total(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")  # equip_nacional = capital
    process = _create_process(client, project, item, estimated_unit_value="500", quantity="1")
    _authorize(client, project, process["id"])
    _create_process(client, project, item, estimated_unit_value="200", quantity="1")  # comprometido

    # valores em R$: colaborador não vê (core/redaction.py)
    assert client.get(f"/projects/{project['id']}/overview", headers=COLAB).status_code == 403
    overview = client.get(f"/projects/{project['id']}/overview", headers=ADMIN).json()
    groups = {g["group"]: g for g in overview["groups"]}
    assert Decimal(groups["capital"]["planned_value"]) == 10000
    assert Decimal(groups["capital"]["executed"]) == 500
    assert Decimal(groups["capital"]["committed"]) == 200
    assert Decimal(groups["capital"]["balance"]) == 9300
    assert Decimal(groups["corrente"]["planned_value"]) == 0
    assert Decimal(overview["total"]["executed"]) == 500 and Decimal(overview["total_executed"]) == 500
    assert overview["items_over_budget"] == 0


# ---------- flexibilidade ----------


def test_balance_policy_warn_lets_overspend_through_with_a_warning(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")  # saldo 10.000
    assert client.patch(f"/projects/{project['id']}", json={"balance_policy": "xpto"}, headers=ADMIN).status_code == 422
    assert client.patch(f"/projects/{project['id']}", json={"balance_policy": "avisar"}, headers=ADMIN).json()["balance_policy"] == "avisar"

    resp = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "Caro", "quantity": "1", "estimated_unit_value": "12000"},
        headers=COLAB,
    )
    assert resp.status_code == 201
    assert any("Saldo insuficiente" in w for w in resp.json()["warnings"])

    # a política é por projeto: voltando a "bloquear", o mesmo pedido é recusado
    client.patch(f"/projects/{project['id']}", json={"balance_policy": "bloquear"}, headers=ADMIN)
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "Caro 2", "quantity": "1", "estimated_unit_value": "12000"},
        headers=COLAB,
    )
    assert resp.status_code == 409


def test_coordinator_can_skip_document_requirement_with_a_reason(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    url = f"/projects/{project['id']}/purchase-processes/{process['id']}/transition"

    # sem documento: recusado, para qualquer um
    assert client.post(url, json={"action": "avancar_cotacao"}, headers=ADMIN).status_code == 409
    # colaborador não pode dispensar nem justificando
    assert client.post(url, json={"action": "avancar_cotacao", "override_reason": "urgente"}, headers=COLAB).status_code == 409
    # coordenador pode, justificando
    resp = client.post(url, json={"action": "avancar_cotacao", "override_reason": "Cotação por e-mail, anexo depois"}, headers=ADMIN)
    assert resp.status_code == 200 and resp.json()["status"] == "cotacao"

    events = client.get(
        f"/projects/{project['id']}/events",
        params={"entity_type": "purchase_process", "entity_id": process["id"]},
        headers=ADMIN,
    ).json()
    moved = next(e for e in events if e["action"] == "avancar_cotacao")
    assert "Cotação por e-mail, anexo depois" in moved["detail"]  # a justificativa fica registrada


def test_override_does_not_bypass_wrong_state_or_missing_role(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    url = f"/projects/{project['id']}/purchase-processes/{process['id']}/transition"
    resp = client.post(url, json={"action": "concluir", "override_reason": "tentando pular"}, headers=ADMIN)
    assert resp.status_code == 409  # estado errado continua recusado


# ---------- histórico ----------


def test_event_history_records_who_did_what(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    _authorize(client, project, process["id"])

    events = client.get(
        f"/projects/{project['id']}/events",
        params={"entity_type": "purchase_process", "entity_id": process["id"]},
        headers=ADMIN,
    ).json()
    actions = [e["action"] for e in reversed(events)]  # do mais antigo ao mais novo
    assert actions == [
        "criado", "documento_enviado", "avancar_cotacao", "solicitar_autorizacao",
        "documento_enviado", "autorizar",
    ]
    authorized = events[0]
    assert authorized["username"] == "admin" and "autorizado" in authorized["detail"]

    # colaborador vê o histórico (quem fez o quê e quando), mas sem o
    # detalhe — que traz valores estimados/finais
    colab_events = client.get(
        f"/projects/{project['id']}/events",
        params={"entity_type": "purchase_process", "entity_id": process["id"]},
        headers=COLAB,
    ).json()
    assert [e["action"] for e in colab_events] == [e["action"] for e in events]
    assert all(e["detail"] == "{}" for e in colab_events)


def test_event_history_is_visible_only_to_members(client):
    project, _item = _project_with_active_budget(client)
    outsider = {"X-Horun-User-Id": "u-out", "X-Horun-User": "out", "X-Horun-Role": "user"}
    assert client.get(f"/projects/{project['id']}/events", headers=outsider).status_code == 403


# ---------- base ----------


def test_process_number_is_normalized_and_unique_per_project(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")
    first = _create_process(client, project, item, estimated_unit_value="100", quantity="1")
    second = _create_process(client, project, item, estimated_unit_value="100", quantity="1")
    base = f"/projects/{project['id']}/purchase-processes"

    resp = client.patch(f"{base}/{first['id']}", json={"process_number": "2024 0077"}, headers=ADMIN)
    assert resp.status_code == 200 and resp.json()["process_number"] == "2024-77"

    clash = client.patch(f"{base}/{second['id']}", json={"process_number": "2024-77"}, headers=ADMIN)
    assert clash.status_code == 409 and "2024-77" in clash.json()["detail"]

    # o mesmo nº em OUTRO projeto é permitido
    other, other_item = _project_with_active_budget_other(client)
    other_process = _create_process(client, other, other_item, estimated_unit_value="100", quantity="1")
    ok = client.patch(
        f"/projects/{other['id']}/purchase-processes/{other_process['id']}", json={"process_number": "2024-77"}, headers=ADMIN
    )
    assert ok.status_code == 200


def _project_with_active_budget_other(client):
    project = client.post("/projects", json={"code": "99.999", "name": "Outro"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "Baseline", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "x", "unit_value": "1000", "planned_quantity": "10"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    return project, item


def test_authorizing_with_a_clashing_process_number_is_a_clean_conflict(client):
    project, item = _project_with_active_budget(client, unit_value="1000", planned_quantity="10")
    first = _create_process(client, project, item, estimated_unit_value="100", quantity="1")
    second = _create_process(client, project, item, estimated_unit_value="100", quantity="1")
    client.patch(f"/projects/{project['id']}/purchase-processes/{first['id']}", json={"process_number": "2024-5"}, headers=ADMIN)

    _upload(client, project["id"], second["id"], "cotacao")
    _transition(client, project["id"], second["id"], "avancar_cotacao")
    _transition(client, project["id"], second["id"], "solicitar_autorizacao")
    _upload(client, project["id"], second["id"], "solicitacao_autorizacao")
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{second['id']}/transition",
        json={"action": "autorizar", "process_number": "2024 5"},
        headers=ADMIN,
    )
    assert resp.status_code == 409 and "nº de processo" in resp.json()["detail"]
    # e o processo continua no estado anterior
    assert client.get(f"/projects/{project['id']}/purchase-processes/{second['id']}", headers=ADMIN).json()["status"] == "aguardando_autorizacao"


def test_upload_over_the_size_limit_is_refused(client, monkeypatch):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    resp = _upload(client, project["id"], process["id"], "cotacao")
    assert resp.status_code == 413
    assert client.get(f"/projects/{project['id']}/purchase-processes/{process['id']}/documents", headers=ADMIN).json() == []


def test_upload_stores_sha256_and_kind(client):
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item)
    resp = _upload(client, project["id"], process["id"], "cotacao")
    assert resp.status_code == 201 and resp.json()["storage_kind"] == "upload"

    events = client.get(
        f"/projects/{project['id']}/events", params={"entity_type": "purchase_process", "entity_id": process["id"]}, headers=ADMIN
    ).json()
    sent = next(e for e in events if e["action"] == "documento_enviado")
    assert re.search(r'"sha256": "[0-9a-f]{64}"', sent["detail"])  # hash do conteúdo no histórico


def test_list_filter_by_category_is_applied_in_the_query(client):
    project, item = _project_with_active_budget(client)
    _create_process(client, project, item)
    base = f"/projects/{project['id']}/purchase-processes"
    assert len(client.get(base, params={"category": "equip_nacional"}, headers=ADMIN).json()) == 1
    assert client.get(base, params={"category": "passagens"}, headers=ADMIN).json() == []
