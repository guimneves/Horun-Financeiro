"""Arquivar/desarquivar e excluir projeto (decisão de 07/10/2026).

Arquivar: coordenador; o projeto some da lista (a menos de
?include_archived=true) e da sincronização automática, mas continua abrindo.
Excluir: só o administrador máximo (nível 1), digitando o código; apaga
tudo do projeto no banco e os anexos enviados ao servidor — nunca o drive.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.core.config import settings
from app.core.files import resolve_path
from app.db.models.audit import AuditEvent
from app.db.models.budget import BudgetItem, BudgetPosition, BudgetRevision
from app.db.models.document import Document
from app.db.models.drive_state import DriveUnlinkedPath
from app.db.models.funding import FundingInstallment
from app.db.models.personnel import Person, PersonnelAssignment
from app.db.models.project import Project, ProjectMembership
from app.db.models.purchase import PurchaseProcess
from app.db.session import engine
from tests.conftest import ADMIN, COLAB
from tests.test_core_roles import ADMIN_MAX, COORD_CORE
from tests.test_purchases import _create_process, _project_with_active_budget, _upload


def _archive(client, project_id, headers=ADMIN, action="archive"):
    return client.post(f"/projects/{project_id}/{action}", headers=headers)


# --- arquivar -----------------------------------------------------------------


def test_coordinator_archives_and_unarchives(client):
    project, _item = _project_with_active_budget(client)

    resp = _archive(client, project["id"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["archived_at"] is not None
    assert resp.json()["archived_by"] == "admin"
    assert _archive(client, project["id"]).status_code == 409  # já arquivado

    resp = _archive(client, project["id"], action="unarchive")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is None and resp.json()["archived_by"] is None
    assert _archive(client, project["id"], action="unarchive").status_code == 409

    with Session(engine) as session:
        actions = session.exec(
            select(AuditEvent.action).where(AuditEvent.project_id == project["id"], AuditEvent.entity_type == "project")
        ).all()
    assert actions == ["projeto_arquivado", "projeto_desarquivado"]


def test_colaborador_cannot_archive(client):
    project, _item = _project_with_active_budget(client)
    assert _archive(client, project["id"], headers=COLAB).status_code == 403
    _archive(client, project["id"])
    assert _archive(client, project["id"], headers=COLAB, action="unarchive").status_code == 403


def test_archived_is_hidden_from_list_but_still_opens(client):
    project, _item = _project_with_active_budget(client)
    other = client.post("/projects", json={"code": "99.001", "name": "Outro"}, headers=ADMIN).json()
    _archive(client, project["id"])

    for headers in (ADMIN, COLAB):
        assert [p["id"] for p in client.get("/projects", headers=headers).json()] == [other["id"]]
        listed = client.get("/projects?include_archived=true", headers=headers).json()
        assert sorted(p["id"] for p in listed) == sorted([project["id"], other["id"]])
        opened = client.get(f"/projects/{project['id']}", headers=headers)
        assert opened.status_code == 200 and opened.json()["archived_at"] is not None
        assert client.get(f"/projects/{project['id']}/balance", headers=headers).status_code == 200


def test_archived_hidden_in_dev_mode_list_too(client, dev_mode):
    project = client.post("/projects", json={"code": "25.465", "name": "P"}, headers=ADMIN).json()
    _archive(client, project["id"])
    assert client.get("/projects", headers=ADMIN).json() == []
    assert [p["id"] for p in client.get("/projects?include_archived=true", headers=ADMIN).json()] == [project["id"]]


def test_auto_sync_skips_archived_projects(client, tmp_path, monkeypatch):
    from app.api import routes_drive
    from app.services import drive_auto_sync

    monkeypatch.setattr(settings, "drive_root", str(tmp_path))
    active = client.post("/projects", json={"code": "25.001", "name": "Ativo"}, headers=ADMIN).json()
    archived = client.post("/projects", json={"code": "25.002", "name": "Arquivado"}, headers=ADMIN).json()
    with Session(engine) as session:
        for p in (active, archived):
            row = session.get(Project, p["id"])
            row.drive_folder = f"Pasta {p['code']}"
            session.add(row)
        session.commit()
    _archive(client, archived["id"])

    seen: list[int] = []

    def fake_plan(session, project, _arg):
        seen.append(project.id)
        raise routes_drive.PlanError("só conferindo")

    monkeypatch.setattr(routes_drive, "build_sync_plan", fake_plan)
    with Session(engine) as session:
        detail = drive_auto_sync.sync_projects(session)
    assert seen == [active["id"]]
    assert archived["id"] not in detail


# --- excluir ------------------------------------------------------------------


@pytest.fixture
def enforce_foreign_keys():
    """O SQLite dos testes não confere chaves estrangeiras por padrão — aqui
    liga, como o Postgres de produção, para a ordem da exclusão valer."""

    def _on(dbapi_connection, _record, _proxy):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "checkout", _on)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    yield
    event.remove(engine, "checkout", _on)


def _full_project(client, tmp_drive: Path):
    """Projeto com orçamento, compras (anexo + documento do drive + nova
    tentativa), equipe, parcelas, membros, desvinculados e histórico."""
    project, item = _project_with_active_budget(client)
    pid = project["id"]
    # uma segunda revisão (rascunho), para haver mais de uma
    client.post(f"/projects/{pid}/revisions", json={"label": "Reformulação", "effective_date": "2025-01-01"}, headers=ADMIN)

    cancelled = _create_process(client, project, item)
    assert _upload(client, pid, cancelled["id"], "cotacao").status_code == 201
    client.post(
        f"/projects/{pid}/purchase-processes/{cancelled['id']}/transition",
        json={"action": "cancelar", "reason": "Preço subiu"}, headers=ADMIN,
    )
    retry = client.post(
        f"/projects/{pid}/purchase-processes",
        json={
            "budget_position_id": item["position_id"], "title": "2ª tentativa",
            "quantity": "1", "estimated_unit_value": "100", "previous_attempt_id": cancelled["id"],
        },
        headers=ADMIN,
    ).json()
    assert _upload(client, pid, retry["id"], "cotacao", filename="b.pdf").status_code == 201

    drive_file = tmp_drive / "Pasta" / "NF 1.pdf"
    drive_file.parent.mkdir(parents=True)
    drive_file.write_bytes(b"arquivo do drive")

    with Session(engine) as session:
        row = session.get(Project, pid)
        row.drive_folder = "Pasta"
        session.add(row)
        position_id = item["position_id"]
        person = Person(project_id=pid, full_name="Pessoa Sintética")
        session.add(person)
        session.flush()
        assignment = PersonnelAssignment(
            project_id=pid, person_id=person.id, budget_position_id=position_id, role_title="Bolsista",
            monthly_rate=Decimal("1000.00"), start_date=date(2024, 1, 1), created_by_user_id="u-admin",
        )
        session.add(assignment)
        session.flush()
        common = dict(content_type="application/pdf", size_bytes=10, uploaded_by_user_id="u", uploaded_by_username="u")
        session.add(Document(
            purchase_process_id=retry["id"], doc_type="nota_fiscal", original_filename="NF 1.pdf",
            storage_path="NF 1.pdf", storage_kind="drive", **common,
        ))
        session.add(Document(
            personnel_assignment_id=assignment.id, doc_type="recibo_pessoal", original_filename="r.pdf",
            storage_path=f"{pid}/inexistente/r.pdf", storage_kind="upload", **common,
        ))
        session.add(FundingInstallment(project_id=pid, number=1, amount=Decimal("5000.00")))
        session.add(DriveUnlinkedPath(project_id=pid, rel_path="x.pdf"))
        session.commit()
        uploads = [
            resolve_path(d.storage_path)
            for d in session.exec(select(Document).where(Document.storage_kind == "upload")).all()
            if resolve_path(d.storage_path).exists()
        ]
    assert len(uploads) == 2
    return project, uploads, drive_file


def _rows_for(session: Session, project_id: int, revision_ids, position_ids, process_ids, assignment_ids) -> dict:
    count = {}
    for model in (
        PurchaseProcess, PersonnelAssignment, Person, BudgetRevision, BudgetPosition,
        FundingInstallment, ProjectMembership, DriveUnlinkedPath, AuditEvent,
    ):
        count[model.__name__] = len(session.exec(select(model).where(model.project_id == project_id)).all())
    count["BudgetItem"] = len(session.exec(select(BudgetItem).where(
        BudgetItem.revision_id.in_(revision_ids) | BudgetItem.position_id.in_(position_ids)  # type: ignore[attr-defined]
    )).all())
    count["Document"] = len(session.exec(select(Document).where(
        Document.purchase_process_id.in_(process_ids)  # type: ignore[union-attr]
        | Document.personnel_assignment_id.in_(assignment_ids)  # type: ignore[union-attr]
    )).all())
    count["Project"] = 1 if session.get(Project, project_id) else 0
    return count


def test_super_admin_deletes_everything_but_the_drive(client, tmp_path, monkeypatch, enforce_foreign_keys):
    monkeypatch.setattr(settings, "drive_root", str(tmp_path))
    project, uploads, drive_file = _full_project(client, tmp_path)
    other = client.post("/projects", json={"code": "99.001", "name": "Outro"}, headers=ADMIN).json()
    pid = project["id"]

    with Session(engine) as session:
        ids = {
            "revision_ids": session.exec(select(BudgetRevision.id).where(BudgetRevision.project_id == pid)).all(),
            "position_ids": session.exec(select(BudgetPosition.id).where(BudgetPosition.project_id == pid)).all(),
            "process_ids": session.exec(select(PurchaseProcess.id).where(PurchaseProcess.project_id == pid)).all(),
            "assignment_ids": session.exec(
                select(PersonnelAssignment.id).where(PersonnelAssignment.project_id == pid)
            ).all(),
        }
        before = _rows_for(session, pid, **ids)
    assert all(n > 0 for n in before.values()), before

    resp = client.request("DELETE", f"/projects/{pid}", json={"confirm_code": "25.465"}, headers=ADMIN_MAX)
    assert resp.status_code == 204, resp.text

    with Session(engine) as session:
        after = _rows_for(session, pid, **ids)
        assert session.get(Project, other["id"]) is not None
    assert all(n == 0 for n in after.values()), after
    assert not any(path.exists() for path in uploads)
    assert drive_file.read_bytes() == b"arquivo do drive"  # o drive nunca é tocado
    assert client.get(f"/projects/{pid}", headers=ADMIN).status_code == 404
    assert [p["id"] for p in client.get("/projects", headers=ADMIN).json()] == [other["id"]]
    assert client.get(f"/projects/{other['id']}", headers=ADMIN).status_code == 200


@pytest.mark.parametrize("headers", [COORD_CORE, ADMIN, COLAB], ids=["nivel-2", "admin-sem-nivel", "colaborador"])
def test_only_super_admin_can_delete(client, headers):
    project, _item = _project_with_active_budget(client)
    resp = client.request("DELETE", f"/projects/{project['id']}", json={"confirm_code": "25.465"}, headers=headers)
    assert resp.status_code == 403
    assert "administrador máximo" in resp.json()["detail"]
    assert client.get(f"/projects/{project['id']}", headers=ADMIN).status_code == 200


def test_delete_requires_typing_the_code(client):
    project, _item = _project_with_active_budget(client)
    for body in ({"confirm_code": "25.46"}, {"confirm_code": ""}, {}):
        resp = client.request("DELETE", f"/projects/{project['id']}", json=body, headers=ADMIN_MAX)
        assert resp.status_code == 422
    resp = client.request("DELETE", f"/projects/{project['id']}", json={"confirm_code": "x"}, headers=ADMIN_MAX)
    assert resp.json()["detail"] == "Digite o código do projeto para confirmar."
    assert client.get(f"/projects/{project['id']}", headers=ADMIN).status_code == 200


def test_delete_unknown_project_is_404(client):
    resp = client.request("DELETE", "/projects/999", json={"confirm_code": "x"}, headers=ADMIN_MAX)
    assert resp.status_code == 404
