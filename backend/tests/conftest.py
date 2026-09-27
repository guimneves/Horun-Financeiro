"""HORUN_DEV_MODE fica desligado nos testes de propósito — os testes de
permissão (coordenador vs colaborador, admin do Core) precisam simular
usuários DIFERENTES via cabeçalho, e em DEV_MODE a identidade é sempre o
mesmo usuário fixo (ver app/core/identity.py)."""

from __future__ import annotations

import os
import tempfile

os.environ["HORUN_DEV_MODE"] = "false"
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["MODULE_DATABASE_URL"] = f"sqlite:///{_db_path}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.db.session import create_db_and_tables, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = {"X-Horun-User-Id": "u-admin", "X-Horun-User": "admin", "X-Horun-Role": "admin"}
COLAB = {"X-Horun-User-Id": "u-colab", "X-Horun-User": "colaborador", "X-Horun-Role": "user"}
OUTSIDER = {"X-Horun-User-Id": "u-outsider", "X-Horun-User": "outsider", "X-Horun-Role": "user"}


@pytest.fixture(autouse=True)
def _fresh_db():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    yield


@pytest.fixture
def client():
    return TestClient(app)
