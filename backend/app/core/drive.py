"""Acesso ao drive do Financeiro (pasta do OneDrive) — leitura e consulta,
nunca escrita. Todo caminho que vem de fora (API) passa por `safe_join`, que
impede sair da pasta do projeto (`..`, caminho absoluto, etc.).
"""

from __future__ import annotations

import os
import posixpath
import sys
from pathlib import Path

from app.core.config import settings
from app.db.models.project import Project


class DriveError(Exception):
    """Drive não configurado, pasta inexistente ou caminho inválido."""


def fs_path(path: str | os.PathLike[str]) -> str:
    """Caminho pronto para o sistema de arquivos. No Windows, caminhos acima
    de 260 caracteres (comuns nas pastas do projeto) só abrem com o prefixo
    `\\\\?\\` — sem ele, listar/abrir falha."""
    absolute = os.path.abspath(os.fspath(path))
    if sys.platform == "win32" and not absolute.startswith("\\\\?\\"):
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return absolute


def drive_root() -> Path:
    if not settings.drive_root:
        raise DriveError("O drive não está configurado neste servidor (defina MODULE_DRIVE_ROOT).")
    root = Path(settings.drive_root)
    if not os.path.isdir(fs_path(root)):
        raise DriveError(f"A raiz do drive não existe ou não está acessível: {root}")
    return root


def safe_join(base: Path, relative: str) -> Path:
    """`base / relative`, garantindo que o resultado continua dentro de `base`.

    O `:` é recusado em QUALQUER segmento, não só no primeiro: no Windows,
    `base.joinpath("pasta", "D:", "x")` troca de unidade e sai da base
    (`D:x`). Depois do join, uma conferência final por `commonpath` cobre o
    que a checagem por segmento não previr."""
    rel = relative.replace("\\", "/").strip("/")
    if rel == "":
        return base
    if "\x00" in rel:
        raise DriveError("Caminho inválido.")
    parts = posixpath.normpath(rel).split("/")
    if any(p == ".." or ":" in p for p in parts):
        raise DriveError("Caminho inválido.")
    result = base.joinpath(*parts)
    base_abs = os.path.abspath(base)
    if os.path.commonpath([base_abs, os.path.abspath(result)]) != base_abs:
        raise DriveError("Caminho inválido.")
    return result


def resolve_drive_folder(drive_folder: str) -> Path:
    """Valida e resolve uma pasta de projeto (relativa à raiz do drive).

    A pasta tem que ser uma subpasta de verdade: `.`/vazio apontariam o
    projeto pra raiz do drive inteiro, e os membros desse projeto passariam
    a navegar nos documentos de todos os outros."""
    normalized = posixpath.normpath(drive_folder.replace("\\", "/").strip("/")) if drive_folder.strip() else ""
    if normalized in ("", "."):
        raise DriveError("Informe uma subpasta do drive, não a raiz.")
    folder = safe_join(drive_root(), drive_folder)
    if not os.path.isdir(fs_path(folder)):
        raise DriveError(f"A pasta do projeto não existe no drive: {drive_folder}")
    return folder


def project_drive_dir(project: Project) -> Path:
    """Pasta do projeto no drive (raiz + `Project.drive_folder`)."""
    if not project.drive_folder:
        raise DriveError("Este projeto ainda não tem pasta do drive configurada.")
    return resolve_drive_folder(project.drive_folder)
