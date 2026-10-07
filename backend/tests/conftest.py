"""HORUN_DEV_MODE fica desligado nos testes de propósito — os testes rodam
como o módulo atrás do Core (papel pelo cargo no Horun, ver
app/core/permissions.py), simulando usuários DIFERENTES via cabeçalho.

O esquema de desenvolvimento (cadastro de membros dá o acesso + senha
mestra) é testado com o fixture `dev_mode`, que liga o DEV_MODE só durante
o teste — os cabeçalhos continuam valendo nele (é o seletor "Ver como")."""

from __future__ import annotations

import os
import tempfile

os.environ["HORUN_DEV_MODE"] = "false"
# Fora do DEV_MODE não há valores padrão para segredos (core/config.py).
os.environ.setdefault("MODULE_SECRET_KEY", "chave-so-dos-testes-" + "x" * 32)
os.environ.setdefault("MODULE_COORDENADOR_PASSWORD", "senha-dos-testes")
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["MODULE_DATABASE_URL"] = f"sqlite:///{_db_path}"
# Uploads dos testes numa pasta temporária — senão caem em ./uploads, dentro
# do projeto.
os.environ["MODULE_UPLOAD_ROOT"] = tempfile.mkdtemp(prefix="financeiro-uploads-")
# O laço da sincronização automática não roda nos testes — os testes dela
# chamam app.services.drive_auto_sync direto. Escrita no drive desligada por
# padrão (os testes de escrita ligam com monkeypatch).
os.environ["MODULE_DRIVE_AUTO_SYNC_MINUTES"] = "0"
os.environ["MODULE_DRIVE_WRITE"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.api.routes_auth import _failed_attempts  # noqa: E402
from app.db.session import create_db_and_tables, engine  # noqa: E402
from app.main import app  # noqa: E402

# Sem X-Horun-Level: "admin" conta como nível 2 (coordenador/a) e "user" como 5
# (app/core/identity.py, parse_level).
ADMIN = {"X-Horun-User-Id": "u-admin", "X-Horun-User": "admin", "X-Horun-Role": "admin"}
COLAB = {"X-Horun-User-Id": "u-colab", "X-Horun-User": "colaborador", "X-Horun-Role": "user"}
OUTSIDER = {"X-Horun-User-Id": "u-outsider", "X-Horun-User": "outsider", "X-Horun-Role": "user"}


@pytest.fixture(autouse=True)
def _fresh_db():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    _failed_attempts.clear()  # contador de tentativas de senha é global
    yield


@pytest.fixture
def client():
    # base_url com /api/: os testes escrevem "/projects/..." e o httpx junta
    # com o prefixo real da API (main.py). Para bater na raiz (ex. /health),
    # use uma URL absoluta: client.get("http://testserver/health").
    return TestClient(app, base_url="http://testserver/api/")


@pytest.fixture
def dev_mode(monkeypatch):
    """Esquema de desenvolvimento (Apresentar_Financeiro.bat): papel pelo
    cadastro de membros e senha mestra (app/core/permissions.py)."""
    from app.core import identity

    monkeypatch.setattr(identity, "DEV_MODE", True)
    return True
