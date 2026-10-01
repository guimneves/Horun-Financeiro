"""Leitura das pastas do drive, planilha de valores, sincronização e consulta
de arquivos. A estrutura de pastas dos testes imita a do projeto real
(Categoria / Item N - descrição / AAAA-NNNN título / arquivos).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.process_number import normalize_process_number
from app.services.drive_scan import classify_document, scan_project_folder
from tests.conftest import ADMIN, COLAB


def test_normalize_process_number_accepts_all_real_formats():
    assert normalize_process_number("2024 3708") == "2024-3708"
    assert normalize_process_number("2024-5616") == "2024-5616"
    assert normalize_process_number("2024_0123") == "2024-123"
    assert normalize_process_number(" 2025-4530 ") == "2025-4530"
    assert normalize_process_number("") is None
    assert normalize_process_number(None) is None
    assert normalize_process_number("a definir") == "a definir"  # não some em silêncio


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("autorizacao_de_fornecimento_9481.pdf", "autorizacao_fornecimento"),
        ("Boleto NF 123.pdf", "boleto"),
        ("2593 DANFE.pdf", "nota_fiscal"),
        ("nf-123.pdf", "nota_fiscal"),
        ("nota1.pdf", "nota_fiscal"),
        ("Nota fiscal atestada.pdf", "nota_fiscal"),
        ("1 - Fornecedor_Proposta.pdf", "cotacao"),
        ("Cotação 4727 B - COPPETEC.pdf", "cotacao"),
        ("pedido_importacao.pdf", "pedido_importacao"),
        ("carta exclusividade 2025.pdf", "outro"),
        ("informe_tecnico.pdf", "outro"),  # "nf" dentro de uma palavra não é nota fiscal
    ],
)
def test_classify_document(filename, expected):
    assert classify_document(filename) == expected


def _touch(path: Path, content: bytes = b"pdf-bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def drive(tmp_path, monkeypatch):
    """Raiz do drive com a pasta de um projeto, no formato real."""
    monkeypatch.setattr(settings, "drive_root", str(tmp_path))
    project = tmp_path / "Guilherme - 25465 Teste"
    consumo = project / "Material de consumo - Nacional" / "Item 1 - Tubos e conexões"
    _touch(consumo / "2024-1001 Tubo inox" / "autorizacao_de_fornecimento_1.pdf")
    _touch(consumo / "2024-1001 Tubo inox" / "NF 123.pdf")
    _touch(consumo / "2024-1001 Tubo inox" / "Cotações" / "1 - Proposta A.pdf")
    _touch(consumo / "2024 1002 Tubo antigo (CANCELADO)" / "proposta.pdf")
    _touch(consumo / "Pasta de anotações" / "x.pdf")  # sem nº de processo
    _touch(consumo / "leia-me.txt")  # arquivo solto no item
    equip = project / "Equipamento e Material Permanente - Nacional" / "Item 1 - Computador"
    _touch(equip / "2024-2002 Computador" / "autorizacao_de_fornecimento.pdf")
    _touch(equip / "2024-2002 Computador" / "Nota fiscal atestada.pdf")
    _touch(project / "Equipamento e Material Permanente - Nacional" / "Item 9 - Que não existe" / "2024-9999 X" / "a.pdf")
    _touch(project / "Equipe Executora" / "x.pdf")
    _touch(project / "1_Afastamento do País" / "Viagem" / "x.pdf")
    _touch(project / "Material de consumo - Nacional" / "Item 3 - Sem processos" / "Documentos" / "y.pdf")

    import openpyxl

    workbook = openpyxl.Workbook()
    consumo_sheet = workbook.active
    consumo_sheet.title = "Material de Consumo"
    consumo_sheet.append(["Material de Consumo Nacional"])
    consumo_sheet.append(["Item", "Nº do Item", "Favorecido", "Descrição", "Valor", "No de Processo COPPETEC"])
    consumo_sheet.append(["x", 1, "Fornecedor A", "Tubo inox", 1500.50, "2024 1001"])
    consumo_sheet.append(["x", 1, "Fornecedor X", "Linha sem nº", 99, "?"])
    equip_sheet = workbook.create_sheet("Equip. Nacional")  # esta aba TEM a coluna "Quantidade"
    equip_sheet.append(["Equipamento Nacional"])
    equip_sheet.append(["Item", "Nº do Item", "Quantidade", "Favorecido", "Descrição", "Valor", "No de Processo COPPETEC"])
    equip_sheet.append(["x", 1, 2, "Dell", "Computador", 7000, "2024 2002"])
    (project / "0_Saldo por item").mkdir()
    workbook.save(project / "0_Saldo por item" / "saldo.xlsx")
    return project


def _project_with_budget(client, drive_folder="Guilherme - 25465 Teste"):
    project = client.post("/projects", json={"code": "25.465", "name": "Maturação Artificial"}, headers=ADMIN).json()
    revision = client.post(
        f"/projects/{project['id']}/revisions",
        json={"label": "Baseline", "effective_date": "2024-01-01"},
        headers=ADMIN,
    ).json()
    for category, number in (("material_consumo_nacional", 1), ("equip_nacional", 1)):
        client.post(
            f"/projects/{project['id']}/revisions/{revision['id']}/items",
            json={
                "category": category, "item_number": number, "description": "Item",
                "unit_value": "1000", "planned_quantity": "5",  # R$ 5.000 por item
            },
            headers=ADMIN,
        )
    client.post(f"/projects/{project['id']}/revisions/{revision['id']}/activate", headers=ADMIN)
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": "u-colab", "username": "colaborador", "role": "colaborador"},
        headers=ADMIN,
    )
    if drive_folder:
        resp = client.patch(f"/projects/{project['id']}", json={"drive_folder": drive_folder}, headers=ADMIN)
        assert resp.status_code == 200, resp.text
    return project


LEDGER = {"ledger_path": "0_Saldo por item/saldo.xlsx"}


def test_scan_folder_recognizes_structure_and_reports_the_rest(drive):
    result = scan_project_folder(str(drive))
    by_number = {p.process_number: p for p in result.processes}

    assert set(by_number) == {"2024-1001", "2024-1002", "2024-2002", "2024-9999"}
    assert by_number["2024-1001"].category == "material_consumo_nacional"
    assert by_number["2024-1001"].item_number == 1
    assert by_number["2024-1001"].title == "Tubo inox"
    assert len(by_number["2024-1001"].files) == 3  # inclui a subpasta "Cotações"
    assert by_number["2024-1001"].inferred_status == "nota_fiscal_emitida"
    assert by_number["2024-1002"].cancelled and by_number["2024-1002"].inferred_status == "cancelado"
    assert by_number["2024-1002"].title == "Tubo antigo"  # "(CANCELADO)" sai do título
    assert by_number["2024-2002"].inferred_status == "concluido"  # nota fiscal atestada

    assert any("Pasta de anotações" in u["path"] for u in result.unrecognized)
    # subpasta sem nº de processo dentro de um item: reportada, nunca forçada a virar processo
    assert any(u["path"].endswith("Item 3 - Sem processos/Documentos") for u in result.unrecognized)
    assert result.loose_files == 1
    ignored = {i["path"] for i in result.ignored_folders}
    assert {"Equipe Executora", "1_Afastamento do País", "0_Saldo por item"} <= ignored


def test_scan_endpoint_is_a_dry_run_and_needs_coordinator(client, drive):
    project = _project_with_budget(client)
    url = f"/projects/{project['id']}/drive/scan"

    assert client.post(url, json=LEDGER, headers=COLAB).status_code == 403

    report = client.post(url, json=LEDGER, headers=ADMIN).json()
    assert report["summary"]["processos_na_pasta"] == 4
    assert report["summary"]["a_criar"] == 3
    assert report["summary"]["sem_item_no_orcamento"] == 1  # Item 9 não existe no orçamento
    by_number = {p["process_number"]: p for p in report["processes"]}
    assert Decimal(by_number["2024-1001"]["value"]) == Decimal("1500.50")
    assert by_number["2024-1001"]["value_source"] == "planilha"
    assert by_number["2024-2002"]["quantity"] == "2.00"  # a coluna "Quantidade" foi achada pelo título
    assert by_number["2024-1002"]["value_source"] == "cancelado"
    assert any("?" in line and "99" in line for line in report["ledger_skipped"])  # o valor pulado aparece

    # nada foi gravado
    assert client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json() == []


def test_sync_creates_processes_and_links_files_without_copying(client, drive):
    project = _project_with_budget(client)
    resp = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["processos_criados"] == 3
    assert resp.json()["arquivos_vinculados"] == 3 + 1 + 2

    processes = {p["process_number"]: p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()}
    tubo, antigo, pc = processes["2024-1001"], processes["2024-1002"], processes["2024-2002"]
    assert tubo["origin"] == "drive_import" and tubo["status"] == "nota_fiscal_emitida"
    assert Decimal(tubo["final_value"]) == Decimal("1500.50")
    assert antigo["status"] == "cancelado" and Decimal(antigo["estimated_value"]) == 0
    assert pc["status"] == "concluido" and pc["completed_at"] is not None
    assert Decimal(pc["estimated_value"]) == Decimal("7000.00") and Decimal(pc["quantity"]) == 2

    docs = client.get(f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents", headers=ADMIN).json()
    assert {d["doc_type"] for d in docs} == {"autorizacao_fornecimento", "nota_fiscal", "cotacao"}
    assert all(d["storage_kind"] == "drive" for d in docs)

    # o saldo passa a refletir o histórico: 5.000 previstos − 1.500,50 realizados
    balance = {b["category"]: b for b in client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()}
    assert Decimal(balance["material_consumo_nacional"]["executed"]) == Decimal("1500.50")
    assert Decimal(balance["equip_nacional"]["executed"]) == Decimal("7000.00")
    assert Decimal(balance["equip_nacional"]["balance"]) == Decimal("-2000.00")  # histórico não é bloqueado


def test_sync_is_idempotent_and_picks_up_new_files(client, drive):
    project = _project_with_budget(client)
    url = f"/projects/{project['id']}/drive/sync"
    client.post(url, json=LEDGER, headers=ADMIN)

    again = client.post(url, json=LEDGER, headers=ADMIN).json()
    assert again["processos_criados"] == 0 and again["arquivos_vinculados"] == 0
    assert len(client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()) == 3

    _touch(drive / "Material de consumo - Nacional" / "Item 1 - Tubos e conexões" / "2024-1001 Tubo inox" / "boleto.pdf")
    third = client.post(url, json=LEDGER, headers=ADMIN).json()
    assert third["processos_criados"] == 0 and third["arquivos_vinculados"] == 1


def test_sync_without_ledger_creates_zero_value_processes_and_says_so(client, drive):
    project = _project_with_budget(client)
    report = client.post(f"/projects/{project['id']}/drive/scan", json={}, headers=ADMIN).json()
    assert report["summary"]["sem_valor"] == 2  # 1001 e 2002; o cancelado não precisa de valor
    resp = client.post(f"/projects/{project['id']}/drive/sync", json={}, headers=ADMIN)
    assert resp.json()["processos_criados"] == 3
    tubo = next(p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json() if p["process_number"] == "2024-1001")
    assert Decimal(tubo["estimated_value"]) == 0


def test_drive_documents_download_but_are_never_deleted_from_disk(client, drive):
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    # processo "autorizado" (não encerrado) para poder remover documento
    processes = client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
    tubo = next(p for p in processes if p["process_number"] == "2024-1001")
    docs = client.get(f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents", headers=ADMIN).json()
    af = next(d for d in docs if d["doc_type"] == "autorizacao_fornecimento")

    download = client.get(
        f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents/{af['id']}/download", headers=COLAB
    )
    assert download.status_code == 200 and download.content == b"pdf-bytes"

    resp = client.delete(f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents/{af['id']}", headers=ADMIN)
    assert resp.status_code == 204
    afile = drive / "Material de consumo - Nacional" / "Item 1 - Tubos e conexões" / "2024-1001 Tubo inox" / "autorizacao_de_fornecimento_1.pdf"
    assert afile.exists()  # o arquivo do drive continua lá

    # e uma nova sincronização o vincula de novo
    again = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN).json()
    assert again["arquivos_vinculados"] == 1


def test_reclassify_document_even_in_closed_process(client, drive):
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    pc = next(p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json() if p["process_number"] == "2024-2002")
    assert pc["status"] == "concluido"
    doc = client.get(f"/projects/{project['id']}/purchase-processes/{pc['id']}/documents", headers=ADMIN).json()[0]
    resp = client.patch(
        f"/projects/{project['id']}/purchase-processes/{pc['id']}/documents/{doc['id']}",
        json={"doc_type": "comprovante_recebimento"},
        headers=COLAB,
    )
    assert resp.status_code == 200 and resp.json()["doc_type"] == "comprovante_recebimento"


def test_browse_and_download_any_file_in_project_folder(client, drive):
    project = _project_with_budget(client)
    root = client.get(f"/projects/{project['id']}/drive/browse", headers=COLAB).json()
    names = {e["name"] for e in root["entries"]}
    assert "Material de consumo - Nacional" in names and "0_Saldo por item" in names

    folder = client.get(
        f"/projects/{project['id']}/drive/browse",
        params={"path": "Material de consumo - Nacional/Item 1 - Tubos e conexões"},
        headers=COLAB,
    ).json()
    assert folder["parent"] == "Material de consumo - Nacional"
    assert any(e["name"] == "leia-me.txt" and not e["is_dir"] for e in folder["entries"])

    file_resp = client.get(
        f"/projects/{project['id']}/drive/file",
        params={"path": "Material de consumo - Nacional/Item 1 - Tubos e conexões/leia-me.txt"},
        headers=COLAB,
    )
    assert file_resp.status_code == 200 and file_resp.content == b"pdf-bytes"


@pytest.mark.parametrize("evil", ["../fora.txt", "..", "a/../../fora", "/etc/passwd", "C:/Windows/win.ini"])
def test_cannot_escape_project_folder(client, drive, evil):
    project = _project_with_budget(client)
    (drive.parent / "fora.txt").write_text("segredo")
    assert client.get(f"/projects/{project['id']}/drive/file", params={"path": evil}, headers=ADMIN).status_code in (404, 409)
    assert client.get(f"/projects/{project['id']}/drive/browse", params={"path": evil}, headers=ADMIN).status_code in (404, 409)


def test_drive_folder_must_exist_and_ledger_must_be_xlsx(client, drive):
    project = _project_with_budget(client, drive_folder=None)
    resp = client.patch(f"/projects/{project['id']}", json={"drive_folder": "Pasta inexistente"}, headers=ADMIN)
    assert resp.status_code == 422
    assert client.patch(f"/projects/{project['id']}", json={"drive_folder": "../fora"}, headers=ADMIN).status_code == 422

    client.patch(f"/projects/{project['id']}", json={"drive_folder": "Guilherme - 25465 Teste"}, headers=ADMIN)
    bad = client.post(f"/projects/{project['id']}/drive/scan", json={"ledger_path": "../x.csv"}, headers=ADMIN)
    assert bad.status_code == 422


@pytest.fixture
def small_drive(tmp_path, monkeypatch):
    """Um processo com pasta só de cotação que está na planilha, e dois lançamentos
    da planilha sem pasta (um com item no orçamento, outro sem)."""
    monkeypatch.setattr(settings, "drive_root", str(tmp_path))
    project = tmp_path / "Proj"
    _touch(project / "Material de consumo - Nacional" / "Item 1 - Tubos" / "2024-4004 Só cotação" / "1 - proposta.pdf")

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Material de Consumo"
    sheet.append(["Material de Consumo Nacional"])
    sheet.append(["Item", "Nº do Item", "Favorecido", "Descrição", "Valor", "No de Processo COPPETEC"])
    sheet.append(["x", 1, "Fornecedor A", "Tubo", 400, "2024 4004"])  # tem pasta, só com cotação
    sheet.append(["x", 1, "Fornecedor Y", "Compra sem pasta", 300, "2024 3003"])  # sem pasta
    sheet.append(["x", 77, "Fornecedor Z", "Item que não existe", 50, "2024 3004"])  # sem pasta e sem item
    workbook.save(project / "saldo.xlsx")
    return project


def test_ledger_promotes_quote_only_folder_to_authorized_and_creates_ledger_only_rows(client, small_drive):
    project = _project_with_budget(client, drive_folder="Proj")
    body = {"ledger_path": "saldo.xlsx"}

    report = client.post(f"/projects/{project['id']}/drive/scan", json=body, headers=ADMIN).json()
    by_number = {p["process_number"]: p for p in report["processes"]}
    assert by_number["2024-4004"]["inferred_status"] == "autorizado"  # a pasta só tinha cotação; a planilha o lançou
    assert any("autorizado" in w for w in by_number["2024-4004"]["warnings"])
    assert by_number["2024-3003"]["action"] == "criar_da_planilha"
    assert by_number["2024-3003"]["files_total"] == 0
    assert by_number["2024-3004"]["action"] == "sem_item_no_orcamento"
    assert report["summary"]["a_criar"] == 1 and report["summary"]["a_criar_so_planilha"] == 1

    sync = client.post(f"/projects/{project['id']}/drive/sync", json=body, headers=ADMIN).json()
    assert sync["processos_criados"] == 2 and sync["arquivos_vinculados"] == 1

    processes = {p["process_number"]: p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()}
    assert processes["2024-4004"]["status"] == "autorizado" and Decimal(processes["2024-4004"]["estimated_value"]) == 400
    assert processes["2024-3003"]["status"] == "autorizado" and processes["2024-3003"]["drive_rel_path"] is None
    assert processes["2024-3003"]["title"] == "Compra sem pasta"

    # tudo que a planilha lança conta como realizado, e nada fica "comprometido"
    balance = {b["category"]: b for b in client.get(f"/projects/{project['id']}/balance", headers=ADMIN).json()}
    assert Decimal(balance["material_consumo_nacional"]["executed"]) == 700
    assert Decimal(balance["material_consumo_nacional"]["committed"]) == 0

    again = client.post(f"/projects/{project['id']}/drive/sync", json=body, headers=ADMIN).json()
    assert again["processos_criados"] == 0 and again["arquivos_vinculados"] == 0  # não duplica


def test_drive_unavailable_is_reported_not_crashing(client, monkeypatch):
    monkeypatch.setattr(settings, "drive_root", None)
    project = _project_with_budget(client, drive_folder=None)
    status = client.get(f"/projects/{project['id']}/drive/status", headers=ADMIN).json()
    assert status["configured"] is False and status["available"] is False
    assert client.post(f"/projects/{project['id']}/drive/scan", json={}, headers=ADMIN).status_code == 409
