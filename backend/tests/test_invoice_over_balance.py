"""Nota fiscal acima do saldo do item: avisa (428), registra só depois de
confirmada e deixa o processo marcado para o sinal de alerta na lista."""

from __future__ import annotations

from tests.conftest import ADMIN, COLAB
from tests.test_parity import _authorize
from tests.test_purchases import _create_process, _project_with_active_budget, _upload


def _invoice(client, project, process, final_value, headers=ADMIN, **extra):
    return client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": "emitir_nota_fiscal", "final_value": final_value, **extra},
        headers=headers,
    )


def _authorized_process(client, estimated="1000", quantity="9"):
    # orçamento do item: 10 × 1000 = 10.000; processo estimado em 9.000 →
    # sobram 1.000 de saldo para a nota fiscal passar do estimado
    project, item = _project_with_active_budget(client)
    process = _create_process(client, project, item, estimated_unit_value=estimated, quantity=quantity)
    _authorize(client, project, process["id"])
    _upload(client, project["id"], process["id"], "nota_fiscal")
    return project, process


def test_invoice_within_balance_is_registered_without_warning(client):
    project, process = _authorized_process(client)
    resp = _invoice(client, project, process, "9800")  # +800, cabe nos 1.000
    assert resp.status_code == 200
    assert resp.json()["status"] == "nota_fiscal_emitida"
    assert resp.json()["over_balance_confirmed_at"] is None


def test_invoice_above_balance_asks_for_confirmation_and_changes_nothing(client):
    project, process = _authorized_process(client)
    resp = _invoice(client, project, process, "10500")  # +1.500, saldo 1.000
    assert resp.status_code == 428
    detail = resp.json()["detail"]
    assert detail == (
        "A nota fiscal de R$ 10.500,00 fica R$ 1.500,00 acima do valor estimado (R$ 9.000,00), "
        "mas o item Nº 1 só tem R$ 1.000,00 de saldo (faltam R$ 500,00). "
        "Confirme para registrar a nota fiscal mesmo assim."
    )
    current = client.get(f"/projects/{project['id']}/purchase-processes/{process['id']}", headers=ADMIN).json()
    assert current["status"] == "autorizado" and current["final_value"] is None


def test_confirmed_invoice_above_balance_is_registered_and_flagged(client):
    project, process = _authorized_process(client)
    resp = _invoice(client, project, process, "10500", confirm_over_balance=True)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "nota_fiscal_emitida"
    assert body["over_balance_confirmed_by"] == "admin"
    assert body["over_balance_confirmed_at"] is not None

    # o sinal aparece na lista (para todos — não é um valor em R$)
    listing = client.get(f"/projects/{project['id']}/purchase-processes", headers=COLAB).json()
    assert listing[0]["over_balance_confirmed_at"] is not None

    # e fica no histórico, com a mensagem do aviso
    events = client.get(
        f"/projects/{project['id']}/events",
        params={"entity_type": "purchase_process", "entity_id": process["id"]},
        headers=ADMIN,
    ).json()
    assert "faltam R$ 500,00" in events[0]["detail"]


def test_over_balance_warning_hides_values_from_collaborator(client):
    project, process = _authorized_process(client)
    resp = _invoice(client, project, process, "10500", headers=COLAB)
    assert resp.status_code == 428
    assert "R$" not in resp.json()["detail"]


def test_invoice_warning_applies_even_with_warn_only_policy(client):
    project, process = _authorized_process(client)
    client.patch(f"/projects/{project['id']}", json={"balance_policy": "avisar"}, headers=ADMIN)
    assert _invoice(client, project, process, "10500").status_code == 428
