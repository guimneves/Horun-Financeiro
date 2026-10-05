"""Avisos pelo Horun Core (sininho + e-mail): quem recebe cada evento, e
`notify()` nunca atrapalha o módulo (sem configuração = nada; Core fora do
ar = só log)."""

from __future__ import annotations

import pytest

from app.core import notify as notify_module
from tests.conftest import ADMIN, COLAB
from tests.test_purchases import _create_process, _project_with_active_budget, _upload

COORD2 = {"X-Horun-User-Id": "u-coord2", "X-Horun-User": "coord2", "X-Horun-Role": "user"}


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []

    def fake_notify(subject, text="", link="", user_ids=(), levels=(), email=True):
        calls.append(
            {"subject": subject, "text": text, "link": link, "user_ids": list(user_ids), "levels": list(levels), "email": email}
        )

    monkeypatch.setattr(notify_module, "notify", fake_notify)
    return calls


def _transition(client, project, process, action, headers=ADMIN, **extra):
    return client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/transition",
        json={"action": action, **extra},
        headers=headers,
    )


def _setup(client):
    project, item = _project_with_active_budget(client)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-coord2", "username": "coord2", "role": "coordenador"},
        headers=ADMIN,
    )
    return project, item


def _awaiting_authorization(client, project, item, headers=COLAB, **process_kwargs):
    process = _create_process(client, project, item, headers=headers, **process_kwargs)
    _upload(client, project["id"], process["id"], "cotacao", headers=headers)
    assert _transition(client, project, process, "avancar_cotacao", headers=headers).status_code == 200
    assert _transition(client, project, process, "solicitar_autorizacao", headers=headers).status_code == 200
    return process


def test_request_authorization_notifies_project_coordinators(client, sent):
    project, item = _setup(client)
    process = _awaiting_authorization(client, project, item)

    assert len(sent) == 1
    call = sent[0]
    assert call["subject"] == "Compra aguardando autorização"
    assert sorted(call["user_ids"]) == ["u-admin", "u-coord2"]
    assert call["link"] == f"/projects/{project['id']}/purchases/{process['id']}"
    assert "Computador novo" in call["text"] and "colaborador" in call["text"]
    assert "R$" not in call["text"]


def test_coordinator_requesting_authorization_is_not_notified_of_own_action(client, sent):
    project, item = _setup(client)
    _awaiting_authorization(client, project, item, headers=ADMIN)
    assert sent[0]["user_ids"] == ["u-coord2"]


def test_authorization_notifies_creator_without_values(client, sent):
    project, item = _setup(client)
    process = _awaiting_authorization(client, project, item)
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao", headers=COLAB)
    sent.clear()

    resp = _transition(client, project, process, "autorizar", vendor="Fornecedor X", process_number="2026-123")
    assert resp.status_code == 200
    assert len(sent) == 1
    call = sent[0]
    assert call["subject"] == "Compra autorizada"
    assert call["user_ids"] == ["u-colab"]
    assert call["link"] == f"/projects/{project['id']}/purchases/{process['id']}"
    assert "2026-123" in call["text"]
    assert "R$" not in call["text"] and "500" not in call["text"]


def test_rejection_notifies_creator_with_reason(client, sent):
    project, item = _setup(client)
    process = _awaiting_authorization(client, project, item)
    sent.clear()

    resp = _transition(client, project, process, "rejeitar", reason="Cotação vencida")
    assert resp.status_code == 200
    assert [c["subject"] for c in sent] == ["Compra rejeitada"]
    assert sent[0]["user_ids"] == ["u-colab"]
    assert "Cotação vencida" in sent[0]["text"]


def test_creator_who_authorizes_own_process_gets_no_notice(client, sent):
    project, item = _setup(client)
    process = _awaiting_authorization(client, project, item, headers=ADMIN)
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao")
    sent.clear()
    _transition(client, project, process, "autorizar", vendor="Fornecedor X")
    # o aviso é chamado, mas sem destinatário (quem criou é quem autorizou)
    assert sent[0]["user_ids"] == []


def test_invoice_over_balance_notifies_coordinators(client, sent):
    project, item = _setup(client)
    # item: 10 × 1000; processo estimado 9 × 1000 → sobra 1.000 de saldo
    process = _awaiting_authorization(client, project, item, estimated_unit_value="1000", quantity="9")
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao", headers=COLAB)
    _transition(client, project, process, "autorizar", vendor="Fornecedor X")
    _upload(client, project["id"], process["id"], "nota_fiscal", headers=COLAB)
    sent.clear()

    # sem confirmar: 428, nada registrado, nenhum aviso
    resp = _transition(client, project, process, "emitir_nota_fiscal", headers=COLAB, final_value="10500")
    assert resp.status_code == 428
    assert sent == []

    resp = _transition(
        client, project, process, "emitir_nota_fiscal", headers=COLAB, final_value="10500", confirm_over_balance=True
    )
    assert resp.status_code == 200
    assert len(sent) == 1
    assert sent[0]["subject"] == "Nota fiscal acima do saldo do item"
    assert sorted(sent[0]["user_ids"]) == ["u-admin", "u-coord2"]
    assert "R$" not in sent[0]["text"]


def test_invoice_within_balance_sends_no_notice(client, sent):
    project, item = _setup(client)
    process = _awaiting_authorization(client, project, item)
    _upload(client, project["id"], process["id"], "solicitacao_autorizacao", headers=COLAB)
    _transition(client, project, process, "autorizar", vendor="Fornecedor X")
    _upload(client, project["id"], process["id"], "nota_fiscal", headers=COLAB)
    sent.clear()
    resp = _transition(client, project, process, "emitir_nota_fiscal", headers=COLAB, final_value="1000")
    assert resp.status_code == 200
    assert sent == []


def test_failed_transition_sends_no_notice(client, sent):
    project, item = _setup(client)
    process = _create_process(client, project, item, headers=COLAB)
    # sem cotação anexada: o guard recusa
    resp = _transition(client, project, process, "avancar_cotacao", headers=COLAB)
    assert resp.status_code == 409
    resp = _transition(client, project, process, "solicitar_autorizacao", headers=COLAB)
    assert resp.status_code == 409
    assert sent == []


# ---------- notify() em si ----------


def test_notify_is_noop_without_configuration(monkeypatch):
    monkeypatch.delenv("HORUN_CORE_URL", raising=False)
    monkeypatch.delenv("HORUN_NOTIFY_TOKEN", raising=False)
    assert notify_module.notify("Assunto", user_ids=["1"]) is None
    monkeypatch.setenv("HORUN_CORE_URL", "http://127.0.0.1:9")
    assert notify_module.notify("Assunto", user_ids=["1"]) is None  # falta a chave


def test_notify_ignores_non_numeric_ids_and_empty_recipients(monkeypatch):
    monkeypatch.setenv("HORUN_CORE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("HORUN_NOTIFY_TOKEN", "chave-de-teste")
    assert notify_module._core_ids(["12", "dev", 7, "12", " 3 "]) == [12, 7, 3]
    assert notify_module.notify("Assunto", user_ids=["dev"]) is None


def test_notify_never_raises_when_core_is_unreachable(monkeypatch):
    monkeypatch.setenv("HORUN_CORE_URL", "http://127.0.0.1:9")  # porta fechada
    monkeypatch.setenv("HORUN_NOTIFY_TOKEN", "chave-de-teste")
    thread = notify_module.notify("Assunto", "texto", "/projects/1", user_ids=["1"], levels=[2])
    assert thread is not None
    thread.join(timeout=10)
    assert not thread.is_alive()


def test_notify_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_send(url, token, payload):
        captured.update(url=url, token=token, payload=payload)

    monkeypatch.setenv("HORUN_CORE_URL", "http://core:8000/")
    monkeypatch.setenv("HORUN_NOTIFY_TOKEN", "chave")
    monkeypatch.setattr(notify_module, "_send", fake_send)
    thread = notify_module.notify("Assunto", "texto", "/projects/1/purchases/2", user_ids=["5"], email=False)
    thread.join(timeout=5)
    assert captured == {
        "url": "http://core:8000",
        "token": "chave",
        "payload": {
            "user_ids": [5], "levels": [], "subject": "Assunto", "text": "texto",
            "link": "/projects/1/purchases/2", "email": False,
        },
    }
