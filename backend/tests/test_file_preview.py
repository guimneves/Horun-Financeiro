"""Ler arquivos na página, sem baixar (pedido do usuário): com `inline`, PDF,
imagem e texto vêm para exibir; qualquer outro tipo continua download —
um HTML/SVG exibido dentro do Horun rodaria script com a sessão de quem
abriu."""

from __future__ import annotations

import pytest

from tests.conftest import ADMIN, COLAB
from tests.test_drive import _project_with_budget, _touch, drive  # noqa: F401 — fixture

FOLDER = "Material de consumo - Nacional/Item 1 - Tubos e conexões"


def _get(client, project_id, name, **params):
    return client.get(
        f"/projects/{project_id}/drive/file", params={"path": f"{FOLDER}/{name}", **params}, headers=COLAB
    )


@pytest.mark.parametrize("name", ["leia-me.txt", "nota.pdf", "foto.JPG"])
def test_previewable_files_are_shown_inline(client, drive, name):  # noqa: F811
    _touch(drive / FOLDER / name)
    project = _project_with_budget(client)
    r = _get(client, project["id"], name, inline="true")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_without_inline_it_is_still_a_download(client, drive):  # noqa: F811
    _touch(drive / FOLDER / "nota.pdf")
    project = _project_with_budget(client)
    assert _get(client, project["id"], "nota.pdf").headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize("name", ["pagina.html", "desenho.svg", "planilha.xlsx"])
def test_unsafe_or_unknown_types_are_never_shown_inline(client, drive, name):  # noqa: F811
    _touch(drive / FOLDER / name, b"<script>alert(1)</script>")
    project = _project_with_budget(client)
    r = _get(client, project["id"], name, inline="true")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")


def test_purchase_document_preview(client, drive):  # noqa: F811
    project = _project_with_budget(client)
    client.post(f"/projects/{project['id']}/drive/sync", json={}, headers=ADMIN)
    process = next(
        p for p in client.get(f"/projects/{project['id']}/purchase-processes", headers=ADMIN).json()
        if p["process_number"] == "2024-1001"
    )
    docs = client.get(f"/projects/{project['id']}/purchase-processes/{process['id']}/documents", headers=ADMIN).json()
    pdf = next(d for d in docs if d["original_filename"].endswith(".pdf"))
    url = f"/projects/{project['id']}/purchase-processes/{process['id']}/documents/{pdf['id']}/download"
    assert client.get(url, params={"inline": "true"}, headers=COLAB).headers["content-disposition"].startswith("inline")
    assert client.get(url, headers=COLAB).headers["content-disposition"].startswith("attachment")


def test_ledger_open_in_excel_gives_a_clear_message(client, drive, monkeypatch):  # noqa: F811
    import openpyxl

    def locked(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(openpyxl, "load_workbook", locked)
    project = _project_with_budget(client)
    r = client.post(
        f"/projects/{project['id']}/drive/scan", json={"ledger_path": "0_Saldo por item/saldo.xlsx"}, headers=ADMIN
    )
    assert r.status_code == 422 and "aberta no Excel" in r.json()["detail"]
