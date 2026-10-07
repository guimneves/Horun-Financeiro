"""Modo módulo (atrás do Horun Core): o papel vem do cargo no Horun
(X-Horun-Level) — níveis 1–2 coordenam todos os projetos, os demais
colaboram em todos; sem cadastro de membros e sem senha mestra
(decisão de 06/10/2026, app/core/permissions.py). No DEV_MODE continua o
esquema antigo."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.core import notify as notify_module
from app.core.security import issue_coordenador_token
from app.db.models.project import ProjectMembership
from app.db.session import engine
from tests.conftest import ADMIN
from tests.test_purchases import _create_process, _project_with_active_budget, _upload


def _person(user_id: str, level: int | None, role: str = "user") -> dict:
    headers = {"X-Horun-User-Id": user_id, "X-Horun-User": user_id, "X-Horun-Role": role}
    if level is not None:
        headers["X-Horun-Level"] = str(level)
    return headers


ADMIN_MAX = _person("10", 1, "admin")
COORD_CORE = _person("11", 2, "admin")


def _new_revision(client, project, headers):
    return client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=headers,
    )


@pytest.mark.parametrize("headers", [ADMIN_MAX, COORD_CORE, ADMIN], ids=["nivel-1", "nivel-2", "admin-sem-nivel"])
def test_levels_1_and_2_coordinate_every_project_without_membership(client, headers):
    project, _item = _project_with_active_budget(client)

    assert client.get(f"/projects/{project['id']}", headers=headers).json()["my_role"] == "coordenador"
    listed = client.get("/projects", headers=headers).json()
    assert [(p["id"], p["my_role"]) for p in listed] == [(project["id"], "coordenador")]
    balance = client.get(f"/projects/{project['id']}/balance", headers=headers).json()
    assert Decimal(balance[0]["balance"]) == Decimal("10000.00")
    assert _new_revision(client, project, headers).status_code == 201


@pytest.mark.parametrize("level", [3, 4, 5, None], ids=["pesquisador", "tecnico", "ic", "sem-nivel"])
def test_other_levels_are_colaborador_everywhere_and_see_no_money(client, level):
    project, item = _project_with_active_budget(client)
    other = client.post("/projects", json={"code": "99.001", "name": "Outro"}, headers=ADMIN).json()
    person = _person(f"2{level or 0}", level)

    listed = client.get("/projects", headers=person).json()
    assert sorted(p["id"] for p in listed) == sorted([project["id"], other["id"]])
    assert {p["my_role"] for p in listed} == {"colaborador"}

    balance = client.get(f"/projects/{project['id']}/balance", headers=person).json()
    assert balance[0]["balance"] is None and balance[0]["planned_value"] is None
    assert isinstance(balance[0]["has_balance"], bool)
    assert _new_revision(client, project, person).status_code == 403
    # colaborador trabalha normalmente (abre processo de compra)
    assert _create_process(client, project, item, headers=person)["status"]
    assert client.get(f"/projects/{project['id']}/events", headers=person).status_code == 200


def test_synthetic_membership_is_never_saved(client):
    project, _item = _project_with_active_budget(client)
    client.get(f"/projects/{project['id']}", headers=_person("30", 4))
    client.get(f"/projects/{project['id']}", headers=ADMIN_MAX)
    with Session(engine) as session:
        users = sorted(m.user_id for m in session.exec(select(ProjectMembership)))
    assert users == ["u-admin", "u-colab"]  # criador + o colaborador cadastrado pelo helper


def test_unknown_project_is_404(client):
    assert client.get("/projects/999", headers=ADMIN_MAX).status_code == 404


def test_coordenador_password_is_ignored_in_module_mode(client):
    project, _item = _project_with_active_budget(client)
    person = _person("40", 5)

    login = client.post("/auth/coordenador-session", json={"password": "senha-dos-testes"}, headers=person)
    assert login.status_code == 409
    assert "cargo no Horun" in login.json()["detail"]

    token, _ = issue_coordenador_token()  # token válido, mas não vale no modo módulo
    headers = {**person, "X-Horun-Coordenador-Token": token}
    assert client.get(f"/projects/{project['id']}/balance", headers=headers).json()[0]["balance"] is None
    assert _new_revision(client, project, headers).status_code == 403
    change = client.post(
        "/auth/coordenador-password",
        json={"current_password": "senha-dos-testes", "new_password": "outra-senha"},
        headers=headers,
    )
    assert change.status_code == 409


def test_whoami_reports_module_role(client):
    me = client.get("/auth/me", headers=_person("50", 3)).json()
    assert me["level"] == 3 and me["dev_mode"] is False
    assert me["roles_from_core"] is True and me["module_role"] == "colaborador"
    me = client.get("/auth/me", headers=COORD_CORE).json()
    assert me["module_role"] == "coordenador" and me["is_core_admin"] is True


def test_dev_mode_keeps_membership_and_password(client, dev_mode):
    project, _item = _project_with_active_budget(client)
    # Nível 1 sem cadastro no projeto: no desenvolvimento, sem acesso.
    assert client.get(f"/projects/{project['id']}", headers=ADMIN_MAX).status_code == 403
    assert client.get("/projects", headers=ADMIN_MAX).json() == []
    me = client.get("/auth/me", headers=ADMIN_MAX).json()
    assert me["roles_from_core"] is False and me["module_role"] is None and me["dev_mode"] is True

    colab = {"X-Horun-User-Id": "u-colab", "X-Horun-User": "colaborador", "X-Horun-Role": "user"}
    login = client.post("/auth/coordenador-session", json={"password": "senha-dos-testes"}, headers=colab)
    assert login.status_code == 200
    headers = {**colab, "X-Horun-Coordenador-Token": login.json()["token"]}
    assert _new_revision(client, project, headers).status_code == 201


# ---------- avisos: projeto sem coordenador marcado cai para os cargos 1–2 ----------


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []

    def fake_notify(subject, text="", link="", user_ids=(), levels=(), email=True):
        calls.append({"subject": subject, "user_ids": list(user_ids), "levels": list(levels)})

    monkeypatch.setattr(notify_module, "notify", fake_notify)
    return calls


def _request_authorization(client, project, item, headers):
    process = _create_process(client, project, item, headers=headers)
    _upload(client, project["id"], process["id"], "cotacao", headers=headers)
    base = f"/projects/{project['id']}/purchase-processes/{process['id']}/transition"
    assert client.post(base, json={"action": "avancar_cotacao"}, headers=headers).status_code == 200
    assert client.post(base, json={"action": "solicitar_autorizacao"}, headers=headers).status_code == 200


def test_notification_falls_back_to_core_levels_without_marked_coordinator(client, sent):
    project, item = _project_with_active_budget(client)
    with Session(engine) as session:
        for member in session.exec(select(ProjectMembership).where(ProjectMembership.role == "coordenador")):
            session.delete(member)
        session.commit()

    _request_authorization(client, project, item, _person("60", 5))
    assert sent[-1]["subject"] == "Compra aguardando autorização"
    assert sent[-1]["user_ids"] == [] and sent[-1]["levels"] == [1, 2]


def test_notification_goes_to_marked_coordinators_when_there_are(client, sent):
    project, item = _project_with_active_budget(client)
    _request_authorization(client, project, item, _person("61", 5))
    assert sent[-1]["user_ids"] == ["u-admin"] and sent[-1]["levels"] == []
