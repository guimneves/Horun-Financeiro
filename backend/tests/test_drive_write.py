"""Sincronização com o drive nos dois sentidos (decisão de 06/10/2026):
anexos copiados para a pasta do processo, pasta "SEM NUMERO" que ganha o
nº, nº lido da autorização de fornecimento, sincronização automática.
Só pastas temporárias e PDFs sintéticos."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models.budget import BudgetPosition
from app.db.models.document import Document
from app.db.models.purchase import PurchaseProcess
from app.db.session import engine
from app.services import drive_auto_sync
from app.services.af_number import extract_af_number, number_from_text
from app.services.drive_scan import scan_project_folder
from app.services.drive_write import retry_pending, sanitize_file_name, sanitize_name
from tests.conftest import ADMIN, COLAB
from tests.test_drive import LEDGER, _project_with_budget, _touch, drive  # noqa: F401 — fixture
from tests.test_drive_agent_mode import _answer, _FakeAgent, agent_mode  # noqa: F401 — fixture

CONSUMO = "Material de consumo - Nacional/Item 1 - Tubos e conexões"
TODAY = datetime.now(timezone.utc).strftime("%d-%m-%Y")


def _pdf(text: str) -> bytes:
    """PDF mínimo válido com uma linha de texto (Helvetica, WinAnsi)."""
    encoded = text.encode("cp1252")
    escaped = encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    stream = b"BT /F1 12 Tf 50 750 Td (" + escaped + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@pytest.fixture
def writable(drive, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "drive_write", True)
    return drive


def _position_id(project_id: int, category: str = "material_consumo_nacional") -> int:
    with Session(engine) as s:
        return s.exec(
            select(BudgetPosition).where(BudgetPosition.project_id == project_id, BudgetPosition.category == category)
        ).one().id


def _new_process(client, project, title="Luvas: nitrílicas/caixa", category="material_consumo_nacional"):
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes",
        json={"budget_position_id": _position_id(project["id"], category), "title": title,
              "quantity": "1", "estimated_unit_value": "10"},
        headers=ADMIN,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload(client, project, process, filename="cotacao.pdf", content=b"pdf-novo", doc_type="cotacao"):
    resp = client.post(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/documents",
        data={"doc_type": doc_type},
        files={"file": (filename, content, "application/pdf")},
        headers=ADMIN,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _docs(client, project, process):
    return client.get(f"/projects/{project['id']}/purchase-processes/{process['id']}/documents", headers=ADMIN).json()


def _process(process_id: int) -> PurchaseProcess:
    with Session(engine) as s:
        return s.get(PurchaseProcess, process_id)


# --- nomes -----------------------------------------------------------------


def test_sanitize_names_for_windows():
    assert sanitize_name('Luvas: nitrílicas/caixa <2> "x"?. ') == "Luvas nitrílicas caixa 2 x"
    assert len(sanitize_name("a" * 200)) == 60
    assert sanitize_name("CON") == "CON_"
    assert sanitize_file_name("..\\pasta\\Nota: fiscal?.PDF") == "Nota fiscal.PDF"


# --- cópia do anexo ----------------------------------------------------------


def test_upload_is_copied_into_a_new_unnumbered_folder_inside_the_existing_item(client, writable):
    project = _project_with_budget(client)
    process = _new_process(client, project)
    doc = _upload(client, project, process)
    assert doc["drive_copy_status"] == "pendente"  # a resposta sai antes da cópia

    [listed] = _docs(client, project, process)
    folder = f"{CONSUMO}/SEM NUMERO {TODAY} Luvas nitrílicas caixa"
    assert listed["drive_copy_status"] == "copiado"
    assert listed["drive_copy_path"] == f"{folder}/cotacao.pdf"
    assert (writable / folder / "cotacao.pdf").read_bytes() == b"pdf-novo"
    assert _process(process["id"]).drive_rel_path == folder
    # o anexo continua guardado no servidor também (download pelo módulo)
    download = client.get(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{doc['id']}/download", headers=ADMIN
    )
    assert download.content == b"pdf-novo"


def test_missing_category_and_item_folders_are_created_with_canonical_names(client, writable):
    (writable.parent / "Projeto vazio").mkdir()
    project = _project_with_budget(client, drive_folder="Projeto vazio")
    process = _new_process(client, project, title="Tubo")
    _upload(client, project, process)
    expected = writable.parent / "Projeto vazio" / "Material de consumo - Nacional" / "Item 1 - Item"
    assert (expected / f"SEM NUMERO {TODAY} Tubo" / "cotacao.pdf").is_file()


def test_numbered_process_uses_the_number_and_never_overwrites(client, writable):
    project = _project_with_budget(client)
    process = _new_process(client, project, title="Seringa")
    client.patch(f"/projects/{project['id']}/purchase-processes/{process['id']}",
                 json={"process_number": "2024 55"}, headers=ADMIN)
    folder = writable / CONSUMO / "2024-55 Seringa"
    _touch(folder / "cotacao.pdf", b"de outra pessoa")
    _upload(client, project, process, content=b"primeira")
    _upload(client, project, process, content=b"segunda")
    assert (folder / "cotacao.pdf").read_bytes() == b"de outra pessoa"  # intocado
    assert (folder / "cotacao (2).pdf").read_bytes() == b"primeira"
    assert (folder / "cotacao (3).pdf").read_bytes() == b"segunda"


def test_writing_disabled_means_no_copy(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    process = _new_process(client, project)
    _upload(client, project, process)
    [doc] = _docs(client, project, process)
    assert doc["drive_copy_status"] == "" and doc["drive_copy_path"] is None
    assert not any("SEM NUMERO" in p.name for p in (drive / CONSUMO).iterdir())


def test_deleting_a_document_never_deletes_the_drive_copy_nor_relinks_it(client, writable):
    project = _project_with_budget(client)
    process = _new_process(client, project, title="Pipeta")
    doc = _upload(client, project, process)
    copy = writable / CONSUMO / f"SEM NUMERO {TODAY} Pipeta" / "cotacao.pdf"
    assert copy.is_file()
    resp = client.delete(f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{doc['id']}", headers=ADMIN)
    assert resp.status_code == 204
    assert copy.is_file()
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    assert _docs(client, project, process) == []


# --- leitura: pastas do próprio módulo ----------------------------------------


def test_scan_recognises_unnumbered_folders(writable):
    _touch(writable / CONSUMO / "SEM NUMERO 06-10-2026 Balão volumétrico" / "proposta.pdf")
    result = scan_project_folder(str(writable))
    [found] = [p for p in result.processes if p.process_number == ""]
    assert found.title == "Balão volumétrico" and found.item_number == 1 and len(found.files) == 1
    assert not any("SEM NUMERO" in u["path"] for u in result.unrecognized)


def test_sync_matches_module_folders_and_skips_module_copies(client, writable):
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    before = len(client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json())
    process = _new_process(client, project, title="Pipeta")
    _upload(client, project, process)
    # alguém põe um arquivo novo na pasta que o módulo criou
    _touch(writable / CONSUMO / f"SEM NUMERO {TODAY} Pipeta" / "NF 9.pdf")
    # e uma pasta "SEM NUMERO" de ninguém aparece
    _touch(writable / CONSUMO / "SEM NUMERO 01-02-2026 Béquer" / "proposta.pdf")

    result = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN).json()
    assert result["processos_criados"] == 1  # só o Béquer; a pasta da Pipeta é do processo existente
    assert result["arquivos_vinculados"] == 2  # NF 9 + proposta do Béquer; a cópia do módulo não
    docs = _docs(client, project, process)
    assert sorted((d["original_filename"], d["storage_kind"]) for d in docs) == [("NF 9.pdf", "drive"), ("cotacao.pdf", "upload")]
    processes = client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
    assert len(processes) == before + 2
    bequer = next(p for p in processes if p["title"] == "Béquer")
    assert bequer["process_number"] is None


# --- o nº chega: a pasta é renomeada --------------------------------------------


def test_number_assignment_moves_the_unnumbered_folder(client, writable):
    project = _project_with_budget(client)
    process = _new_process(client, project, title="Pipeta")
    _upload(client, project, process)
    old = writable / CONSUMO / f"SEM NUMERO {TODAY} Pipeta"
    _touch(old / "Cotações" / "2 - outra.pdf")  # subpasta posta à mão
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)  # vincula a subpasta

    resp = client.patch(f"/projects/{project['id']}/purchase-processes/{process['id']}",
                        json={"process_number": "2025/321"}, headers=ADMIN)
    assert resp.status_code == 200, resp.text
    new = writable / CONSUMO / "2025-321 Pipeta"
    assert (new / "cotacao.pdf").is_file() and (new / "Cotações" / "2 - outra.pdf").is_file()
    assert not old.exists()  # modo local: a sobra vazia é apagada
    stored = _process(process["id"])
    assert stored.drive_rel_path == f"{CONSUMO}/2025-321 Pipeta" and not stored.drive_rename_pending
    paths = {d["original_filename"]: d for d in _docs(client, project, process)}
    assert paths["cotacao.pdf"]["drive_copy_path"] == f"{CONSUMO}/2025-321 Pipeta/cotacao.pdf"
    download = client.get(
        f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{paths['2 - outra.pdf']['id']}/download",
        headers=ADMIN,
    )
    assert download.status_code == 200
    # sincronizar de novo não cria nada
    again = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN).json()
    assert again["processos_criados"] == 0 and again["arquivos_vinculados"] == 0


# --- nº lido da autorização de fornecimento -----------------------------------


def test_af_number_regex_and_pdf_extraction():
    assert number_from_text("xx AUTORIZAÇÃO DE COMPRA 2025/10736 yy") == "2025-10736"
    assert number_from_text("Autorizacao de Compra Nº 2024 / 0123") == "2024-123"
    assert number_from_text("nada aqui") is None
    assert extract_af_number(_pdf("AUTORIZAÇÃO DE COMPRA 2024/123")) == "2024-123"
    assert extract_af_number(b"isto nao e pdf") is None


def test_af_upload_fills_the_number_and_renames_the_folder(client, writable):
    project = _project_with_budget(client)
    process = _new_process(client, project, title="Pipeta")
    _upload(client, project, process)
    doc = _upload(client, project, process, filename="af.pdf", content=_pdf("AUTORIZAÇÃO DE COMPRA 2024/123"),
                  doc_type="autorizacao_fornecimento")
    assert doc["warning"] is None
    stored = _process(process["id"])
    assert stored.process_number == "2024-123"
    folder = writable / CONSUMO / "2024-123 Pipeta"
    assert (folder / "cotacao.pdf").is_file() and (folder / "af.pdf").is_file()
    history = client.get(f"/projects/{project['id']}/purchase-processes/{process['id']}", headers=ADMIN)
    assert history.json()["process_number"] == "2024-123"


def test_af_with_a_different_or_taken_number_only_warns(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    a = _new_process(client, project, title="A")
    b = _new_process(client, project, title="B")
    client.patch(f"/projects/{project['id']}/purchase-processes/{a['id']}", json={"process_number": "2024-1"}, headers=ADMIN)
    doc = _upload(client, project, a, filename="af.pdf", content=_pdf("AUTORIZAÇÃO DE COMPRA 2024/2"),
                  doc_type="autorizacao_fornecimento")
    assert "diferente do cadastrado 2024-1" in doc["warning"]
    doc = _upload(client, project, b, filename="af.pdf", content=_pdf("AUTORIZAÇÃO DE COMPRA 2024/1"),
                  doc_type="autorizacao_fornecimento")
    assert "já é do processo" in doc["warning"]
    assert _process(a["id"]).process_number == "2024-1" and _process(b["id"]).process_number is None


def test_sync_reads_the_number_of_a_linked_af(client, writable):
    project = _project_with_budget(client)
    _touch(writable / CONSUMO / "SEM NUMERO 01-02-2026 Béquer" / "autorizacao_de_fornecimento_7.pdf",
           _pdf("AUTORIZAÇÃO DE COMPRA 2026/77"))
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    bequer = next(p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
                  if p["title"] == "Béquer")
    assert bequer["process_number"] == "2026-77"
    assert (writable / CONSUMO / "2026-77 Béquer" / "autorizacao_de_fornecimento_7.pdf").is_file()


# --- sincronização automática -------------------------------------------------


@pytest.fixture
def auto_on(monkeypatch):
    monkeypatch.setattr(settings, "drive_auto_sync_minutes", 30)


def test_auto_sync_pass_links_new_files_and_records_the_result(client, drive, auto_on):  # noqa: F811
    project = _project_with_budget(client)
    assert drive_auto_sync.run_auto_sync(engine) == "ok"
    processes = client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
    assert {p["process_number"] for p in processes} >= {"2024-1001", "2024-2002"}
    status = client.get(f"/projects/{project['id']}/drive/status", headers=COLAB).json()
    assert status["auto_sync"]["enabled"] and status["auto_sync"]["last_status"] == "ok"
    assert status["auto_sync"]["new_files"] == 6 and status["auto_sync"]["last_run_at"]

    _touch(drive / CONSUMO / "2024-1001 Tubo inox" / "boleto.pdf")
    assert drive_auto_sync.run_auto_sync(engine) == "not_due"  # dentro do intervalo
    assert drive_auto_sync.run_auto_sync(engine, force=True) == "ok"
    assert client.get(f"/projects/{project['id']}/drive/status", headers=COLAB).json()["auto_sync"]["new_files"] == 1


def test_auto_sync_disabled_with_zero_minutes(client, drive):  # noqa: F811
    assert drive_auto_sync.run_auto_sync(engine) == "disabled"


def test_auto_sync_is_skipped_when_the_agent_is_offline(client, drive, agent_mode, auto_on):  # noqa: F811
    _project_with_budget(client)
    assert drive_auto_sync.run_auto_sync(engine) == "skipped"
    with Session(engine) as s:
        state = drive_auto_sync.get_state(s)
        assert state.last_status == "pulada" and state.last_run_at is None and state.lease_until is None


# --- modo agente -------------------------------------------------------------


class _WritingAgent(_FakeAgent):
    """Agente falso que também grava e move — como o Horun Agent com a pasta
    em "read-write" (`mode="read"` simula a pasta só leitura)."""

    def __init__(self, root: Path, mode: str = "read-write"):
        super().__init__(root)
        self.mode = mode

    def poll_once(self) -> None:
        for task in self.http.get("/agent/tasks", headers=self.headers).json()["tasks"]:
            self.ops.append(task["op"])
            self.http.post(f"/agent/tasks/{task['id']}/result", json=self._handle(task), headers=self.headers)

    def _handle(self, task: dict) -> dict:
        target = self.root.joinpath(*[p for p in (task.get("path") or "").split("/") if p])
        if task["op"] == "write_file":
            if self.mode != "read-write":
                return {"ok": False, "error": "sem permissão para gravar", "code": "read_only"}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(task["content_base64"]))  # o agente real sobrescreve
            return {"ok": True}
        if task["op"] == "move_files":
            if self.mode == "read":
                return {"ok": False, "error": "sem permissão para mover", "code": "read_only"}
            moves = json.loads(base64.b64decode(task["content_base64"]))["moves"]
            done = []
            for m in moves:
                src = self.root.joinpath(*m["from"].split("/"))
                dst = self.root.joinpath(*m["to"].split("/"))
                if dst.exists():
                    return {"ok": False, "error": "já existe um arquivo com esse nome"}
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                done.append(m["to"])
            return {"ok": True, "paths": done}
        return _answer(self.root, task)


def test_copy_and_rename_through_the_agent(client, writable, agent_mode):  # noqa: F811
    agent = _WritingAgent(writable.parent).start()
    try:
        project = _project_with_budget(client)
        process = _new_process(client, project, title="Pipeta")
        _upload(client, project, process)
        old = writable / CONSUMO / f"SEM NUMERO {TODAY} Pipeta"
        assert (old / "cotacao.pdf").read_bytes() == b"pdf-novo"
        _upload(client, project, process)  # mesmo nome: o servidor confere antes (o agente sobrescreveria)
        assert (old / "cotacao (2).pdf").is_file()

        client.patch(f"/projects/{project['id']}/purchase-processes/{process['id']}",
                     json={"process_number": "2024-77"}, headers=ADMIN)
        new = writable / CONSUMO / "2024-77 Pipeta"
        assert (new / "cotacao.pdf").is_file() and (new / "cotacao (2).pdf").is_file()
        assert old.is_dir() and not any(old.iterdir())  # pelo agente a pasta vazia fica
        assert "write_file" in agent.ops and "move_files" in agent.ops
        # a sobra vazia não vira processo novo
        result = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN).json()
        assert not any(p["title"] == "Pipeta" and p["process_number"] is None
                       for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json())
        assert result["arquivos_vinculados"] == 6  # só os da pasta de teste; nenhuma cópia do módulo
    finally:
        agent.stop()


def test_read_only_agent_folder_marks_the_copy_as_error(client, writable, agent_mode):  # noqa: F811
    agent = _WritingAgent(writable.parent, mode="read").start()
    try:
        project = _project_with_budget(client)
        process = _new_process(client, project)
        _upload(client, project, process)
        [doc] = _docs(client, project, process)
        assert doc["drive_copy_status"] == "erro"
        assert "só para leitura" in doc["drive_copy_error"] and "read-write" in doc["drive_copy_error"]
    finally:
        agent.stop()


def test_offline_agent_leaves_the_copy_pending_and_the_retry_finishes_it(client, writable, agent_mode):  # noqa: F811
    project = _project_with_budget(client)
    process = _new_process(client, project, title="Pipeta")
    _upload(client, project, process)
    [doc] = _docs(client, project, process)
    assert doc["drive_copy_status"] == "pendente" and "offline" in doc["drive_copy_error"]

    agent = _WritingAgent(writable.parent).start()
    try:
        with Session(engine) as s:
            stored = s.get(Document, doc["id"])
            stored.uploaded_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            s.add(stored)
            s.commit()
            assert retry_pending(s)["copias"] == 1
        [doc] = _docs(client, project, process)
        assert doc["drive_copy_status"] == "copiado"
        assert (writable / CONSUMO / f"SEM NUMERO {TODAY} Pipeta" / "cotacao.pdf").is_file()
    finally:
        agent.stop()
