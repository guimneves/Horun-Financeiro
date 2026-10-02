"""Modo agente do drive sobre o pacote único do servidor do agente (o mesmo
do RE7S): rotas montadas num app mínimo, um "agente" falso numa thread
respondendo list_tree/read_file sobre uma pasta temporária.

Independe de app.main (que nesta branch ainda não importa — ver
docs/ESTADO_E_PLANOS.md §7); por isso roda também com `--noconftest`."""

from __future__ import annotations

import base64
import os
import tempfile
import threading
import time

os.environ.setdefault("HORUN_DEV_MODE", "false")
if "MODULE_DATABASE_URL" not in os.environ:
    _fd, _path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    os.environ["MODULE_DATABASE_URL"] = f"sqlite:///{_path}"

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.api import routes_agent  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import create_db_and_tables, engine  # noqa: E402
from app.services import agent_bridge  # noqa: E402

ADMIN = {"X-Horun-User-Id": "1", "X-Horun-User": "admin", "X-Horun-Role": "admin"}


@pytest.fixture()
def client():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    app = FastAPI()
    app.include_router(routes_agent.router)
    return TestClient(app)


@pytest.fixture()
def drive(tmp_path):
    (tmp_path / "Proj" / "Passagens").mkdir(parents=True)
    (tmp_path / "Proj" / "(CANCELADO) 12").mkdir()
    (tmp_path / "Proj" / "Passagens" / "a.pdf").write_bytes(b"%PDF" * 100)
    return tmp_path


def _enroll(client, version="0.4.0"):
    code = client.post("/agent/enroll-codes", headers=ADMIN).json()["code"]
    token = client.post("/agent/enroll", json={"enroll_code": code, "device_name": "PC"}).json()["device_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Horun-Agent-Version": version}
    client.get("/agent/tasks", headers=headers)
    return headers


def _fake_agent_answer(drive, task):
    rel = (task.get("path") or "").strip("/")
    base = drive / rel
    if task["op"] == "list_tree":
        if not base.is_dir():
            return {"ok": False, "error": "pasta não encontrada", "code": "not_found"}
        entries = [
            {"path": p.relative_to(drive).as_posix(), "is_dir": p.is_dir(), "size": None if p.is_dir() else p.stat().st_size}
            for p in sorted(base.rglob("*"))
        ]
        return {"ok": True, "entries": entries}
    if task["op"] == "read_file":
        if not base.is_file():
            return {"ok": False, "error": "arquivo não encontrado", "code": "not_found"}
        data = base.read_bytes()
        args = task.get("args") or {}
        off = args.get("offset", 0)
        length = args.get("length") or len(data)
        return {"ok": True, "content_base64": base64.b64encode(data[off:off + length]).decode(), "size": len(data)}
    return {"ok": False, "error": "operação desconhecida", "code": "unknown_op"}


def _with_agent(client, headers, drive, fn):
    out: dict = {}

    def target():
        try:
            out["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            out["error"] = exc

    t = threading.Thread(target=target)
    t.start()
    deadline = time.monotonic() + 10
    while t.is_alive() and time.monotonic() < deadline:
        for task in client.get("/agent/tasks", headers=headers).json()["tasks"]:
            client.post(f"/agent/tasks/{task['id']}/result", json=_fake_agent_answer(drive, task), headers=headers)
        time.sleep(0.02)
    t.join(5)
    if "error" in out:
        raise out["error"]
    return out.get("value")


def test_list_tree_includes_empty_process_folders(client, drive):
    headers = _enroll(client)
    tree = _with_agent(client, headers, drive, lambda: agent_bridge.list_tree("financeiro", "Proj", recursive=True, timeout=5))
    assert [(e.path, e.is_dir) for e in tree] == [
        ("Proj/(CANCELADO) 12", True),
        ("Proj/Passagens", True),
        ("Proj/Passagens/a.pdf", False),
    ]


def test_read_bytes_in_chunks(client, drive, monkeypatch):
    monkeypatch.setattr(settings, "agent_chunk_bytes", 64)
    headers = _enroll(client)
    data = _with_agent(client, headers, drive, lambda: agent_bridge.read_bytes("financeiro", "Proj/Passagens/a.pdf", timeout=5))
    assert data == b"%PDF" * 100


def test_file_above_the_limit_is_refused(client, drive):
    headers = _enroll(client)
    with pytest.raises(agent_bridge.AgentTaskError) as info:
        _with_agent(client, headers, drive, lambda: agent_bridge.read_bytes(
            "financeiro", "Proj/Passagens/a.pdf", max_bytes=10, timeout=5))
    assert info.value.code == "too_large"


def test_missing_file_is_recognized(client, drive):
    headers = _enroll(client)
    with pytest.raises(agent_bridge.AgentTaskError) as info:
        _with_agent(client, headers, drive, lambda: agent_bridge.read_bytes("financeiro", "Proj/nao.pdf", timeout=5))
    assert agent_bridge.file_not_found(info.value)


def test_offline_agent_fails_fast(client):
    with pytest.raises(agent_bridge.AgentOfflineError):
        agent_bridge.read_bytes("financeiro", "x.pdf", timeout=5)


def test_old_agent_cannot_list_folders_and_reads_whole_files(client, drive):
    headers = _enroll(client, version="0.2.0")
    assert agent_bridge.agent_state().online and not agent_bridge.agent_state().extended
    with pytest.raises(agent_bridge.AgentTooOldError):
        agent_bridge.list_tree("financeiro", "Proj", recursive=True, timeout=1)
    data = _with_agent(client, headers, drive, lambda: agent_bridge.read_bytes("financeiro", "Proj/Passagens/a.pdf", timeout=5))
    assert data == b"%PDF" * 100


def test_admin_routes_require_core_admin(client):
    user = {"X-Horun-User-Id": "2", "X-Horun-User": "x", "X-Horun-Role": "user"}
    assert client.post("/agent/enroll-codes", headers=user).status_code == 403
