from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from app.core.config import settings
from tests.conftest import ADMIN, COLAB


def _project_with_personnel_position(client):
    project = client.post("/projects", json={"code": "25.465", "name": "Maturação Artificial"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={
            "category": "equipe_executora", "item_number": 1, "description": "Bolsista Doutorado",
            "unit_value": "3000", "planned_quantity": "12",
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


def test_create_person_and_assignment_computes_accrual(client):
    project, item = _project_with_personnel_position(client)

    person = client.post(
        f"/projects/{project['id']}/personnel", json={"full_name": "Renato Silva"}, headers=ADMIN
    ).json()

    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "Bolsista Doutorado", "monthly_rate": "3000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()

    assert assignment["person_name"] == "Renato Silva"
    assert assignment["status"] == "ativo"
    assert Decimal(assignment["accrued_value"]) >= 0


def test_assignment_rejected_for_non_personnel_category(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()

    resp = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "X", "monthly_rate": "1", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    )
    assert resp.status_code == 422


def test_colaborador_cannot_create_assignment(client):
    project, item = _project_with_personnel_position(client)
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()

    resp = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "X", "monthly_rate": "1", "start_date": "2024-01-01",
        },
        headers=COLAB,
    )
    assert resp.status_code == 403


def test_closing_assignment_freezes_accrual_and_frees_committed_balance(client):
    project, item = _project_with_personnel_position(client)
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "Renato"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "Bolsista", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()

    closed = client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/close",
        json={"end_date": "2024-04-01"},
        headers=ADMIN,
    ).json()
    assert closed["status"] == "encerrado"
    assert Decimal(closed["accrued_value"]) == Decimal("4000.00")  # jan, fev, mar, abr (regra da planilha)
    assert Decimal(closed["committed_future_value"]) == 0

    balance = client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()
    assert Decimal(balance[0]["executed"]) == Decimal("4000.00")
    assert Decimal(balance[0]["committed"]) == 0


def test_assignment_documents_upload_and_list(client):
    project, item = _project_with_personnel_position(client)
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "Renato"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "Bolsista", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()

    upload = client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents",
        data={"period_label": "2024-01"},
        files={"file": ("recibo_janeiro.pdf", b"conteudo fake", "application/pdf")},
        headers=ADMIN,
    )
    assert upload.status_code == 201
    assert upload.json()["doc_type"] == "recibo_pessoal"

    docs = client.get(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents", headers=ADMIN
    ).json()
    assert len(docs) == 1
    assert docs[0]["period_label"] == "2024-01"


def _assignment(client):
    project, item = _project_with_personnel_position(client)
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "Renato"}, headers=ADMIN).json()
    assignment = client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": item["position_id"],
            "role_title": "Bolsista", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    ).json()
    return project, assignment


def _upload_receipt(client, project, assignment, content=b"conteudo fake"):
    return client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents",
        data={"period_label": "2024-01"},
        files={"file": ("recibo.pdf", content, "application/pdf")},
        headers=ADMIN,
    )


def test_receipt_upload_is_audited_with_hash(client):
    project, assignment = _assignment(client)
    assert _upload_receipt(client, project, assignment).status_code == 201
    events = client.get(
        f"/projects/{project['id']}/events",
        params={"entity_type": "personnel_assignment", "entity_id": assignment["id"]},
        headers=ADMIN,
    ).json()
    assert [e["action"] for e in events] == ["documento_enviado"]
    # sha256 de b"conteudo fake"
    assert json.loads(events[0]["detail"])["sha256"] == hashlib.sha256(b"conteudo fake").hexdigest()


def test_receipt_upload_over_the_size_limit_is_refused(client, monkeypatch):
    project, assignment = _assignment(client)
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert _upload_receipt(client, project, assignment).status_code == 413
    docs = client.get(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/documents", headers=ADMIN
    ).json()
    assert docs == []


def test_closed_assignment_does_not_accept_new_receipts(client):
    project, assignment = _assignment(client)
    client.post(
        f"/projects/{project['id']}/personnel-assignments/{assignment['id']}/close",
        json={"end_date": "2024-04-01"},
        headers=ADMIN,
    )
    assert _upload_receipt(client, project, assignment).status_code == 409
