"""Importar quem ocupa cada vaga da Equipe Executora, da aba "Equipe
Executora" da planilha de acompanhamento. Planilha SINTÉTICA (nomes
inventados — repositório público)."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl

from app.services.accrual import compute_accrual
from app.services.personnel_import import parse_personnel_sheet
from tests.conftest import ADMIN, COLAB
from tests.test_budget_import import HEADER_PERSONNEL


def _sheet() -> bytes:
    wb = openpyxl.Workbook()
    budget = wb.active
    budget.title = "Saldo por Item"
    for row in [
        ["Elemento de Despesa: Equipe Executora"],
        HEADER_PERSONNEL,
        [1, "Vaga técnico A", "Técnico", "Ressarcimento - HH", "-", 24, 5, 500, 100, 600, 14400, 3],
        [2, "PD - Vaga B", "PD", "Bolsa de pesquisa", "BOLSA - PÓS-DOUTORADO", 12, 40, 7000, 0, 7000, 84000, 2],
        ["VALOR TOTAL DO ELEMENTO DE DESPESA"],
    ]:
        budget.append(row)

    team = wb.create_sheet("Equipe Executora")
    team.append(["Equipe Executora", None, None, None, None, None, None, None, None, None, None, None, None, "Utilizado"])
    team.append(["Item", "Membro", "Profissional", None, "Início", None, "Fim", None, "Período", "Valor", "Valor total"])
    team.append([None, None, None, "Situação", "Referência", "Pagto", "Referência", "Pagto"])
    team.append([1, "Vaga técnico A", "Ana Teste", "Ativo", datetime(2024, 5, 1), datetime(2024, 6, 1),
                 datetime(2026, 9, 17), datetime(2026, 10, 17), 29, 600, 17400])
    team.append([2, "PD - Vaga B", "Bruno Teste", "Encerrado", datetime(2024, 10, 1), datetime(2024, 11, 1),
                 datetime(2025, 10, 1), datetime(2025, 11, 1), 13, 7000, 91000])
    team.append([2, "PD - Vaga B", "Carla Teste", "Ativo", datetime(2026, 1, 1), datetime(2026, 2, 1),
                 datetime(2026, 9, 17), datetime(2026, 10, 17), 9, 7000, 63000])
    team.append([9, "Vaga que não está no orçamento", "Davi Teste", "Ativo", datetime(2026, 1, 1), None, None, None, 1, 100, 100])
    team.append([41, 0, None, None, None, None, None, None, None, 0, 0])  # reservadas, sem pessoa
    team.append([None, "#N/A", None, None, None, None, None, None, None, 0, 0])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_parse_reads_who_occupies_each_vacancy():
    result = parse_personnel_sheet(_sheet())
    assert [(a.item_number, a.person_name, a.status) for a in result.assignments] == [
        (1, "Ana Teste", "ativo"), (2, "Bruno Teste", "encerrado"), (2, "Carla Teste", "ativo"), (9, "Davi Teste", "ativo"),
    ]
    bruno = result.assignments[1]
    assert (bruno.start_date, bruno.end_date, bruno.monthly_rate) == (date(2024, 10, 1), date(2025, 10, 1), Decimal("7000"))
    assert result.assignments[0].end_date is None  # ativo: sem fim (a planilha põe a data do dia)
    assert result.warnings == []


def test_module_accrual_matches_the_sheet_on_the_sheet_date():
    # a planilha calcula até a data em que foi atualizada (17/09/2026)
    for a in parse_personnel_sheet(_sheet()).assignments[:3]:
        accrual = compute_accrual(
            start_date=a.start_date, end_date=a.end_date, status=a.status, monthly_rate=a.monthly_rate,
            today=date(2026, 9, 17),
        )
        assert accrual.accrued_value == a.sheet_value


def _upload(client, url, headers=ADMIN, **form):
    return client.post(
        url, headers=headers, data=form,
        files={"file": ("planilha.xlsx", _sheet(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def _project_with_budget(client):
    project = client.post("/projects", json={"code": "99.002", "name": "Projeto sintético"}, headers=ADMIN).json()
    r = _upload(client, f"/projects/{project['id']}/budget-import", effective_date="2024-05-01")
    assert r.status_code == 201, r.text
    client.post(f"/projects/{project['id']}/revisions/{r.json()['revision']['id']}/activate", headers=ADMIN)
    return project


def test_preview_flags_missing_vacancies_and_writes_nothing(client):
    project = _project_with_budget(client)
    r = _upload(client, f"/projects/{project['id']}/personnel-import/preview")
    assert r.status_code == 200, r.text
    rows = {row["person_name"]: row for row in r.json()["rows"]}
    assert rows["Ana Teste"]["position_found"] is True
    assert rows["Davi Teste"]["position_found"] is False
    assert Decimal(r.json()["sheet_total"]) == Decimal("171500")
    assert client.get(f"/projects/{project['id']}/personnel", headers=ADMIN).json() == []


def test_import_creates_people_and_assignments_and_is_idempotent(client):
    project = _project_with_budget(client)
    r = _upload(client, f"/projects/{project['id']}/personnel-import")
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["people_created"], body["assignments_created"], body["skipped"]) == (3, 3, 1)
    assert any("vaga 9" in w for w in body["warnings"])

    assignments = {a["person_name"]: a for a in client.get(f"/projects/{project['id']}/personnel-assignments", headers=ADMIN).json()}
    assert assignments["Bruno Teste"]["status"] == "encerrado" and assignments["Bruno Teste"]["end_date"] == "2025-10-01"
    assert assignments["Carla Teste"]["status"] == "ativo" and assignments["Carla Teste"]["end_date"] is None
    assert Decimal(assignments["Bruno Teste"]["accrued_value"]) == Decimal("91000")

    again = _upload(client, f"/projects/{project['id']}/personnel-import").json()
    assert (again["people_created"], again["assignments_created"]) == (0, 0)
    preview = _upload(client, f"/projects/{project['id']}/personnel-import/preview").json()
    assert all(row["already_imported"] for row in preview["rows"] if row["position_found"])


def test_only_the_coordinator_imports_personnel(client):
    project = _project_with_budget(client)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"}, headers=ADMIN,
    )
    assert _upload(client, f"/projects/{project['id']}/personnel-import", headers=COLAB).status_code == 403
