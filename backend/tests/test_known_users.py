"""Diretório de usuários já vistos — populado automaticamente pelo
middleware a partir do cabeçalho de identidade, sem depender de nenhuma
lista do Horun Core (o módulo não tem acesso a ela)."""

from __future__ import annotations

from tests.conftest import ADMIN, COLAB, OUTSIDER


def test_request_registers_the_caller_as_known_user(client):
    client.get("/projects", headers=ADMIN)
    users = client.get("/known-users", headers=ADMIN).json()
    assert any(u["user_id"] == "u-admin" and u["username"] == "admin" for u in users)


def test_multiple_callers_all_get_registered(client):
    client.get("/projects", headers=ADMIN)
    client.get("/projects", headers=COLAB)
    client.get("/projects", headers=OUTSIDER)

    users = client.get("/known-users", headers=ADMIN).json()
    ids = {u["user_id"] for u in users}
    assert {"u-admin", "u-colab", "u-outsider"} <= ids


def test_username_change_updates_existing_record_instead_of_duplicating(client):
    client.get("/projects", headers={"X-Horun-User-Id": "u-1", "X-Horun-User": "Nome Antigo", "X-Horun-Role": "user"})
    client.get("/projects", headers={"X-Horun-User-Id": "u-1", "X-Horun-User": "Nome Novo", "X-Horun-Role": "user"})

    users = client.get("/known-users", headers=ADMIN).json()
    matching = [u for u in users if u["user_id"] == "u-1"]
    assert len(matching) == 1
    assert matching[0]["username"] == "Nome Novo"
