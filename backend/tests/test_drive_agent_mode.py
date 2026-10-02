"""O drive no modo agente (`MODULE_DRIVE_MODE=agent`): as mesmas rotas e os
mesmos cenários de `test_drive.py`, mas o backend não enxerga a pasta — um
"agente" falso numa thread consulta `/api/agent/tasks` e responde
`list_tree`/`read_file` sobre a pasta de teste, como o Horun Agent 0.4.0
faria no PC do OneDrive."""

from __future__ import annotations

import base64
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.conftest import ADMIN, COLAB
from tests.test_drive import LEDGER, _project_with_budget, _touch, drive  # noqa: F401 — fixture


def _answer(root: Path, task: dict) -> dict:
    args = task.get("args") or {}
    base = root.joinpath(*[p for p in (task.get("path") or "").split("/") if p])
    if task["op"] == "list_tree":
        if not base.is_dir():
            return {"ok": False, "error": "pasta não encontrada", "code": "not_found"}
        found = base.rglob("*") if args.get("recursive", True) else base.iterdir()
        entries = [
            {"path": p.relative_to(root).as_posix(), "is_dir": p.is_dir(), "size": None if p.is_dir() else p.stat().st_size}
            for p in sorted(found)
        ]
        return {"ok": True, "entries": entries}
    if task["op"] == "read_file":
        if not base.is_file():
            return {"ok": False, "error": "arquivo não encontrado", "code": "not_found"}
        data = base.read_bytes()
        offset = args.get("offset", 0)
        length = args.get("length") or len(data)
        return {"ok": True, "content_base64": base64.b64encode(data[offset:offset + length]).decode(), "size": len(data)}
    return {"ok": False, "error": f"operação desconhecida: {task['op']!r}", "code": "unknown_op"}


class _FakeAgent:
    def __init__(self, root: Path, version: str = "0.4.0"):
        self.root = root
        self.http = TestClient(app, base_url="http://testserver/api/")
        code = self.http.post("/agent/enroll-codes", headers=ADMIN).json()["code"]
        token = self.http.post("/agent/enroll", json={"enroll_code": code, "device_name": "PC-ONEDRIVE"}).json()[
            "device_token"
        ]
        self.headers = {"Authorization": f"Bearer {token}", "X-Horun-Agent-Version": version}
        self.ops: list[str] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def poll_once(self) -> None:
        for task in self.http.get("/agent/tasks", headers=self.headers).json()["tasks"]:
            self.ops.append(task["op"])
            self.http.post(f"/agent/tasks/{task['id']}/result", json=_answer(self.root, task), headers=self.headers)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            time.sleep(0.02)

    def start(self) -> "_FakeAgent":
        self.poll_once()  # primeira consulta: registra versão e "visto em"
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(5)


@pytest.fixture
def agent_mode(monkeypatch):
    monkeypatch.setattr(settings, "drive_mode", "agent")
    monkeypatch.setattr(settings, "drive_agent_root", "financeiro")
    monkeypatch.setattr(settings, "agent_task_timeout_seconds", 5.0)


@pytest.fixture
def agent(drive, agent_mode):  # noqa: F811
    fake = _FakeAgent(drive.parent).start()  # a raiz do drive = o root "financeiro" do agente
    yield fake
    fake.stop()


def test_scan_and_sync_through_the_agent(client, agent):
    project = _project_with_budget(client)
    report = client.post(f"/projects/{project['id']}/drive/scan", json=LEDGER, headers=ADMIN).json()
    assert report["summary"]["processos_na_pasta"] == 4
    by_number = {p["process_number"]: p for p in report["processes"]}
    assert Decimal(by_number["2024-1001"]["value"]) == Decimal("1500.50")  # a planilha veio pelo agente
    assert by_number["2024-1002"]["value_source"] == "cancelado"

    resp = client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["processos_criados"] == 3
    assert resp.json()["arquivos_vinculados"] == 3 + 1 + 2
    assert "list_tree" in agent.ops and "read_file" in agent.ops


def test_same_result_as_local_mode(client, drive, monkeypatch):  # noqa: F811
    project = _project_with_budget(client)
    local = client.post(f"/projects/{project['id']}/drive/scan", json=LEDGER, headers=ADMIN).json()

    monkeypatch.setattr(settings, "drive_mode", "agent")
    fake = _FakeAgent(drive.parent).start()
    try:
        remote = client.post(f"/projects/{project['id']}/drive/scan", json=LEDGER, headers=ADMIN).json()
    finally:
        fake.stop()
    assert remote == local


def test_browse_and_download_through_the_agent(client, agent):
    project = _project_with_budget(client)
    root = client.get(f"/projects/{project['id']}/drive/browse", headers=COLAB).json()
    names = [e["name"] for e in root["entries"]]
    assert "Material de consumo - Nacional" in names and "0_Saldo por item" in names
    # pastas antes dos arquivos, sem diferenciar maiúsculas — igual ao modo local
    assert names == sorted(names, key=lambda n: (not any(e["name"] == n and e["is_dir"] for e in root["entries"]), n.casefold()))

    path = "Material de consumo - Nacional/Item 1 - Tubos e conexões/leia-me.txt"
    file_resp = client.get(f"/projects/{project['id']}/drive/file", params={"path": path}, headers=COLAB)
    assert file_resp.status_code == 200 and file_resp.content == b"pdf-bytes"
    assert "attachment" in file_resp.headers["content-disposition"]

    missing = client.get(f"/projects/{project['id']}/drive/file", params={"path": "nao-existe.pdf"}, headers=COLAB)
    assert missing.status_code == 404


def test_drive_document_download_through_the_agent(client, agent):
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json=LEDGER, headers=ADMIN)
    tubo = next(
        p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
        if p["process_number"] == "2024-1001"
    )
    docs = client.get(f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents", headers=ADMIN).json()
    resp = client.get(
        f"/projects/{project['id']}/purchase-processes/{tubo['id']}/documents/{docs[0]['id']}/download", headers=COLAB
    )
    assert resp.status_code == 200 and resp.content == b"pdf-bytes"


def test_status_reports_agent_online_without_calling_it(client, agent):
    project = _project_with_budget(client)
    before = len(agent.ops)
    status = client.get(f"/projects/{project['id']}/drive/status", headers=COLAB).json()
    assert status["mode"] == "agent" and status["available"] is True and status["message"] is None
    assert len(agent.ops) == before  # o estado não manda tarefa ao PC


def test_agent_offline_fails_fast_with_a_clear_message(client, drive, agent_mode):  # noqa: F811
    project = _project_with_budget(client)
    status = client.get(f"/projects/{project['id']}/drive/status", headers=COLAB).json()
    assert status["available"] is False and "offline" in status["message"]

    started = time.monotonic()
    resp = client.post(f"/projects/{project['id']}/drive/scan", json={}, headers=ADMIN)
    assert resp.status_code == 409 and "offline" in resp.json()["detail"]
    assert time.monotonic() - started < 2  # não espera o prazo inteiro


def test_old_agent_is_told_to_update(client, drive, agent_mode):  # noqa: F811
    project = _project_with_budget(client)
    fake = _FakeAgent(drive.parent, version="0.2.0").start()
    try:
        status = client.get(f"/projects/{project['id']}/drive/status", headers=COLAB).json()
        assert status["available"] is False and "0.4.0" in status["message"]
        resp = client.post(f"/projects/{project['id']}/drive/scan", json={}, headers=ADMIN)
        assert resp.status_code == 409 and "0.4.0" in resp.json()["detail"]
    finally:
        fake.stop()


def test_project_folder_is_saved_without_the_pc_on_in_agent_mode(client, drive, agent_mode):  # noqa: F811
    # sem agente nenhum conectado: salvar a pasta não pode depender do PC
    project = _project_with_budget(client, drive_folder=None)
    resp = client.patch(f"/projects/{project['id']}", json={"drive_folder": "Outra pasta"}, headers=ADMIN)
    assert resp.status_code == 200, resp.text
    # mas a sintaxe continua validada
    bad = client.patch(f"/projects/{project['id']}", json={"drive_folder": "../fora"}, headers=ADMIN)
    assert bad.status_code == 422


@pytest.mark.parametrize("evil", ["../fora.txt", "pasta/D:/segredo.txt", "/etc/passwd"])
def test_cannot_escape_project_folder_through_the_agent(client, agent, evil):
    project = _project_with_budget(client)
    resp = client.get(f"/projects/{project['id']}/drive/file", params={"path": evil}, headers=ADMIN)
    assert resp.status_code in (404, 409)
    assert "fora" not in resp.text or resp.status_code != 200


def test_new_files_are_picked_up_on_the_next_sync(client, agent, drive):  # noqa: F811
    project = _project_with_budget(client)
    url = f"/projects/{project['id']}/drive/sync"
    client.post(url, json=LEDGER, headers=ADMIN)
    _touch(drive / "Material de consumo - Nacional" / "Item 1 - Tubos e conexões" / "2024-1001 Tubo inox" / "boleto.pdf")
    again = client.post(url, json=LEDGER, headers=ADMIN).json()
    assert again["processos_criados"] == 0 and again["arquivos_vinculados"] == 1
