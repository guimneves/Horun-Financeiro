"""Senha mestra de coordenador — login, elevação de sessão via header,
redação de valores monetários pra quem não é coordenador, e troca de
senha (única, compartilhada por todo o módulo)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import settings
from tests.conftest import ADMIN, COLAB

DEFAULT_PASSWORD = settings.default_coordenador_password

# A senha mestra só existe no modo de desenvolvimento (decisão de 06/10/2026);
# no modo módulo ela é ignorada (tests/test_core_roles.py).
pytestmark = pytest.mark.usefixtures("dev_mode")


def _project_with_budget(client):
    project = client.post("/projects", json={"code": "25.465", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equip_nacional", "item_number": 1, "description": "X", "unit_value": "1000", "planned_quantity": "10"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    return project, item


def _login(client, password=DEFAULT_PASSWORD, headers=COLAB):
    return client.post("/auth/coordenador-session", json={"password": password}, headers=headers)


def test_login_with_wrong_password_fails(client):
    resp = _login(client, "senha-errada")
    assert resp.status_code == 401


def test_login_with_default_password_succeeds(client):
    resp = _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["expires_at"] > 0


def test_colaborador_sees_null_values_without_token(client):
    project, _item = _project_with_budget(client)
    balance = client.get(f"/projects/{project['id']}/balance", headers=COLAB).json()
    assert balance[0]["balance"] is None
    assert balance[0]["planned_value"] is None
    assert isinstance(balance[0]["has_balance"], bool)


def test_colaborador_sees_real_values_with_valid_coordenador_token(client):
    project, _item = _project_with_budget(client)
    token = _login(client).json()["token"]
    headers = {**COLAB, "X-Horun-Coordenador-Token": token}

    balance = client.get(f"/projects/{project['id']}/balance", headers=headers).json()
    assert Decimal(balance[0]["balance"]) == Decimal("10000.00")


def test_token_also_elevates_role_for_coordenador_only_actions(client):
    project, _item = _project_with_budget(client)
    token = _login(client).json()["token"]
    headers = {**COLAB, "X-Horun-Coordenador-Token": token}

    # criar revisao normalmente exige coordenador — colaborador comum tomaria 403
    resp = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=headers,
    )
    assert resp.status_code == 201


def test_invalid_token_does_not_elevate(client):
    project, _item = _project_with_budget(client)
    headers = {**COLAB, "X-Horun-Coordenador-Token": "token-invalido"}
    resp = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Reformulação", "effective_date": "2025-01-01"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_change_password_requires_valid_token(client):
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-123"},
    )
    assert resp.status_code == 401


def test_change_password_requires_correct_current_password(client):
    token = _login(client).json()["token"]
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": "senha-errada", "new_password": "nova-senha-123"},
        headers={"X-Horun-Coordenador-Token": token},
    )
    assert resp.status_code == 401


def test_change_password_then_old_password_stops_working(client):
    token = _login(client).json()["token"]
    resp = client.post(
        "/auth/coordenador-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-123"},
        headers={"X-Horun-Coordenador-Token": token},
    )
    assert resp.status_code == 204

    assert _login(client, DEFAULT_PASSWORD).status_code == 401
    assert _login(client, "nova-senha-123").status_code == 200


def test_purchase_process_values_redacted_for_colaborador(client):
    project, item = _project_with_budget(client)
    process = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": item["position_id"], "title": "X", "quantity": "2", "estimated_unit_value": "500"},
        headers=ADMIN,
    ).json()
    assert Decimal(process["estimated_value"]) == Decimal("1000.00")  # criador (coordenador) ve normalmente

    as_colab = client.get(
        f"/projects/{project['id']}/purchase-processes/{process['id']}", headers=COLAB
    ).json()
    assert as_colab["estimated_value"] is None
    assert as_colab["estimated_unit_value"] is None
    assert as_colab["status"] == process["status"]  # dados operacionais continuam visiveis


def test_personnel_assignment_values_redacted_for_colaborador(client):
    project = client.post("/projects", json={"code": "1", "name": "X"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions", json={"label": "B", "effective_date": "2024-01-01"}, headers=ADMIN
    ).json()
    personnel_item = client.post(
        f"/projects/{project['id']}/revisions/{revision['id']}/items",
        json={"category": "equipe_executora", "item_number": 1, "description": "Y", "unit_value": "1000", "planned_quantity": "1"},
        headers=ADMIN,
    ).json()
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    person = client.post(f"/projects/{project['id']}/personnel", json={"full_name": "X"}, headers=ADMIN).json()
    client.post(
        f"/projects/{project['id']}/personnel-assignments",
        json={
            "person_id": person["id"], "budget_position_id": personnel_item["position_id"],
            "role_title": "X", "monthly_rate": "1000", "start_date": "2024-01-01",
        },
        headers=ADMIN,
    )

    assignments = client.get(f"/projects/{project['id']}/personnel-assignments", headers=COLAB).json()
    assert assignments[0]["monthly_rate"] is None
    assert assignments[0]["accrued_value"] is None
    assert assignments[0]["person_name"] == "X"  # dados nao-monetarios continuam visiveis


# ---------- endurecimento (repositório público) ----------


def test_login_is_locked_after_repeated_wrong_passwords(client):
    for _ in range(5):
        assert _login(client, "chute").status_code == 401
    # nem a senha certa entra durante o bloqueio
    assert _login(client).status_code == 429
    # o bloqueio é por pessoa: outra identidade continua podendo tentar
    assert _login(client, headers=ADMIN).status_code == 200


def test_successful_login_resets_the_failure_counter(client):
    for _ in range(4):
        _login(client, "chute")
    assert _login(client).status_code == 200
    for _ in range(4):
        assert _login(client, "chute").status_code == 401
    assert _login(client).status_code == 200


def test_login_requires_core_identity(client, monkeypatch):
    from app.core import identity

    # Fora do DEV_MODE: sem os cabeçalhos do Core, nem chega à senha.
    monkeypatch.setattr(identity, "DEV_MODE", False)
    assert client.post("/auth/coordenador-session", json={"password": DEFAULT_PASSWORD}).status_code == 401


def test_without_initial_password_coordinator_login_is_unavailable(client, monkeypatch):
    from sqlmodel import Session

    from app.db import session as db_session
    from app.db.models.module_settings import ModuleSettings

    with Session(db_session.engine) as s:
        s.delete(s.get(ModuleSettings, 1))
        s.commit()
    from app.core import identity

    monkeypatch.setattr(settings, "default_coordenador_password", "")
    # No DEV_MODE haveria a senha provisória; fora dele, sem senha nada é criado.
    monkeypatch.setattr(identity, "DEV_MODE", False)
    db_session._ensure_module_settings()  # sem senha: não cria nada
    monkeypatch.setattr(identity, "DEV_MODE", True)
    resp = _login(client)
    assert resp.status_code == 503
    assert "MODULE_COORDENADOR_PASSWORD" in resp.json()["detail"]


def test_production_refuses_to_start_without_a_strong_secret_key(monkeypatch):
    import pytest

    from app.core.config import check_production_settings

    for weak in ("", "curta"):
        monkeypatch.setattr(settings, "secret_key", weak)
        with pytest.raises(RuntimeError, match="MODULE_SECRET_KEY"):
            check_production_settings(dev_mode=False)
        check_production_settings(dev_mode=True)  # em dev, tolera


def test_token_signed_with_another_key_is_rejected(monkeypatch):
    from app.core import security

    token, _ = security.issue_coordenador_token()
    assert security.verify_coordenador_token(token)
    monkeypatch.setattr(settings, "secret_key", "outra-chave-" + "y" * 32)
    assert not security.verify_coordenador_token(token)
