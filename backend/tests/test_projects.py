from __future__ import annotations

from tests.conftest import ADMIN, COLAB, OUTSIDER


def test_create_project_requires_core_admin(client):
    resp = client.post("/projects", json={"code": "1", "name": "X"}, headers=COLAB)
    assert resp.status_code == 403


def test_create_project_makes_creator_coordenador(client):
    resp = client.post("/projects", json={"code": "25.465", "name": "Maturação Artificial"}, headers=ADMIN)
    assert resp.status_code == 201
    body = resp.json()
    assert body["my_role"] == "coordenador"
    assert body["code"] == "25.465"


def test_duplicate_project_code_rejected(client):
    client.post("/projects", json={"code": "25.465", "name": "A"}, headers=ADMIN)
    resp = client.post("/projects", json={"code": "25.465", "name": "B"}, headers=ADMIN)
    assert resp.status_code == 409


def test_non_member_cannot_read_project(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    resp = client.get(f"/projects/{project['id']}", headers=OUTSIDER)
    assert resp.status_code == 403


def test_coordenador_can_add_colaborador_who_can_then_read(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()

    add = client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    assert add.status_code == 201

    resp = client.get(f"/projects/{project['id']}", headers=COLAB)
    assert resp.status_code == 200
    assert resp.json()["my_role"] == "colaborador"


def test_colaborador_cannot_add_members(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    resp = client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-outsider", "username": "outsider", "role": "colaborador"},
        headers=COLAB,
    )
    assert resp.status_code == 403
