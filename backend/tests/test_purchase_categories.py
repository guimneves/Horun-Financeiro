"""Tipos de despesa liberados para compra (pedido de 07/10/2026): os
coordenadores decidem quais tipos de despesa do orçamento recebem compras
novas. Sem decisão registrada, o tipo está liberado."""

from __future__ import annotations

import json

from sqlalchemy import create_engine, inspect
from sqlmodel import Session, SQLModel, select

from app.db import session as db_session
from app.db.models.audit import AuditEvent
from app.db.models.budget import ProjectPurchaseCategory
from app.db.session import engine
from tests.conftest import ADMIN, COLAB
from tests.test_core_roles import ADMIN_MAX

CLOSED = "Este tipo de despesa não está liberado para compras"


def _project(client, code="99.001"):
    project = client.post("/projects", json={"code": code, "name": "Projeto sintético"}, headers=ADMIN).json()
    pid = project["id"]
    revision = client.post(
        f"/projects/{pid}/revisions", json={"label": "Baseline", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    items = {}
    for category, number in [("equip_nacional", 1), ("equip_nacional", 2), ("passagens", 1), ("equipe_executora", 1)]:
        items[(category, number)] = client.post(
            f"/projects/{pid}/revisions/{revision['id']}/items",
            json={"category": category, "item_number": number, "description": f"Item {number}",
                  "unit_value": "1000", "planned_quantity": "10"},
            headers=ADMIN,
        ).json()
    client.post(f"/projects/{pid}/revisions/{revision['id']}/activate", headers=ADMIN)
    return pid, items


def _set(client, pid, category, open_, headers=ADMIN):
    return client.put(f"/projects/{pid}/purchase-categories/{category}", json={"open": open_}, headers=headers)


def _state(client, pid, headers=ADMIN):
    return {c["category"]: c for c in client.get(f"/projects/{pid}/purchase-categories", headers=headers).json()}


def _create(client, pid, position_id, headers=ADMIN):
    return client.post(
        f"/projects/{pid}/purchase-processes",
        json={"budget_position_id": position_id, "title": "Compra", "quantity": "1", "estimated_unit_value": "100"},
        headers=headers,
    )


def test_categories_start_open_except_personnel(client):
    pid, _items = _project(client)
    for headers in (ADMIN, COLAB):  # o colaborador também lê (modal de nova compra)
        state = _state(client, pid, headers=headers)
        assert state["equip_nacional"]["open"] is True
        assert state["equip_nacional"]["item_count"] == 2
        assert state["passagens"]["item_count"] == 1
        assert state["diarias"]["item_count"] == 0
        assert state["equipe_executora"]["open"] is False  # não usa o fluxo de compra
        assert state["equip_nacional"]["label"].startswith("Equipamento")
        assert state["equip_nacional"]["group"] == "capital"


def test_only_coordinators_open_or_close(client):
    pid, _items = _project(client)
    assert _set(client, pid, "equip_nacional", False, headers=COLAB).status_code == 403
    assert _state(client, pid)["equip_nacional"]["open"] is True

    resp = _set(client, pid, "equip_nacional", False)
    assert resp.status_code == 200
    assert resp.json()["open"] is False
    assert resp.json()["updated_by"] == "admin"
    state = _state(client, pid)
    assert state["equip_nacional"]["open"] is False
    assert state["passagens"]["open"] is True  # outro tipo não muda

    assert _set(client, pid, "equip_nacional", True).json()["open"] is True
    assert _state(client, pid)["equip_nacional"]["open"] is True


def test_personnel_and_unknown_categories_are_rejected(client):
    pid, _items = _project(client)
    assert _set(client, pid, "equipe_executora", True).status_code == 422
    assert _set(client, pid, "nao_existe", False).status_code == 404


def test_decision_is_per_project(client):
    pid, _items = _project(client)
    other, _ = _project(client, code="99.002")
    _set(client, pid, "passagens", False)
    assert _state(client, other)["passagens"]["open"] is True


def test_open_close_is_audited(client):
    pid, _items = _project(client)
    _set(client, pid, "passagens", False)
    _set(client, pid, "passagens", False)  # sem mudança, sem evento
    _set(client, pid, "passagens", True)
    with Session(engine) as session:
        events = session.exec(select(AuditEvent).where(AuditEvent.entity_type == "purchase_category")).all()
    assert [e.action for e in events] == ["compra_fechada", "compra_liberada"]
    assert json.loads(events[0].detail)["categoria"] == "passagens"
    assert events[0].username == "admin"


def test_creation_blocked_on_closed_category_for_everyone(client):
    pid, items = _project(client)
    position = items[("equip_nacional", 2)]["position_id"]
    _set(client, pid, "equip_nacional", False)
    for headers in (ADMIN, COLAB):
        resp = _create(client, pid, position, headers=headers)
        assert resp.status_code == 409
        assert CLOSED in resp.json()["detail"]
        assert "Orçamento" in resp.json()["detail"]
    assert client.get(f"/projects/{pid}/purchase-processes", headers=ADMIN).json() == []

    # o coordenador libera e a compra passa
    _set(client, pid, "equip_nacional", True)
    assert _create(client, pid, position, headers=COLAB).status_code == 201


def test_creation_allowed_on_open_category(client):
    pid, items = _project(client)
    _set(client, pid, "equip_nacional", False)
    assert _create(client, pid, items[("passagens", 1)]["position_id"], headers=COLAB).status_code == 201


def test_closing_does_not_touch_existing_purchases(client):
    pid, items = _project(client)
    process = _create(client, pid, items[("equip_nacional", 1)]["position_id"]).json()
    before = client.get(f"/projects/{pid}/balance", headers=ADMIN).json()

    _set(client, pid, "equip_nacional", False)

    same = client.get(f"/projects/{pid}/purchase-processes/{process['id']}", headers=ADMIN).json()
    assert same["status"] == process["status"]
    assert same["budget_position_id"] == process["budget_position_id"]
    edit = client.patch(
        f"/projects/{pid}/purchase-processes/{process['id']}", json={"title": "Compra editada"}, headers=ADMIN
    )
    assert edit.status_code == 200
    upload = client.post(
        f"/projects/{pid}/purchase-processes/{process['id']}/documents",
        data={"doc_type": "cotacao"}, files={"file": ("cotacao.pdf", b"conteudo fake", "application/pdf")},
        headers=ADMIN,
    )
    assert upload.status_code == 201, upload.text
    moved = client.post(
        f"/projects/{pid}/purchase-processes/{process['id']}/transition", json={"action": "avancar_cotacao"}, headers=ADMIN
    )
    assert moved.status_code == 200, moved.text  # a compra existente segue o fluxo
    after = client.get(f"/projects/{pid}/balance", headers=ADMIN).json()
    assert [r["committed"] for r in after] == [r["committed"] for r in before]


def test_deleting_the_project_removes_its_decisions(client):
    pid, _items = _project(client, code="25.465")
    _set(client, pid, "passagens", False)
    resp = client.request("DELETE", f"/projects/{pid}", json={"confirm_code": "25.465"}, headers=ADMIN_MAX)
    assert resp.status_code == 204, resp.text
    with Session(engine) as session:
        assert session.exec(select(ProjectPurchaseCategory)).all() == []


def test_existing_database_gets_the_table_and_everything_stays_open(tmp_path, monkeypatch):
    old = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with old.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE project (id INTEGER PRIMARY KEY, code VARCHAR NOT NULL, name VARCHAR)')
    monkeypatch.setattr(db_session, "engine", old)

    SQLModel.metadata.create_all(old)  # o que create_db_and_tables() faz ao subir
    db_session._run_migrations()

    assert inspect(old).has_table("projectpurchasecategory")
    with Session(old) as session:
        assert session.exec(select(ProjectPurchaseCategory)).all() == []  # sem linha = liberado
