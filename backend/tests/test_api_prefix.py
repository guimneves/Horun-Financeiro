"""O módulo encaixa no Core só se a API estiver sob /api (o gateway manda
`/m/financeiro/api/...` pro backend e o resto pro frontend) e o /health
ficar na raiz (Prompt_Horun_Modulo.md, seções 5 e 6)."""

from __future__ import annotations

from tests.conftest import ADMIN


def test_health_fica_na_raiz(client):
    resp = client.get("http://testserver/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_responde_sob_prefixo(client):
    assert client.get("http://testserver/api/projects", headers=ADMIN).status_code == 200


def test_api_nao_responde_sem_prefixo(client):
    assert client.get("http://testserver/projects", headers=ADMIN).status_code == 404
