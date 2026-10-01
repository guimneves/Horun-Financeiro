"""Utilitários de caminho do drive do Financeiro (pasta do OneDrive) — só
leitura, nunca escrita. Todo caminho que vem de fora (API) passa por
`join_rel`/`safe_join`, que impedem sair da pasta do projeto (`..`, caminho
absoluto, letra de unidade etc.).
"""

from __future__ import annotations

import os
import posixpath
import sys
from pathlib import Path

from app.core.config import settings


class DriveError(Exception):
    """Drive não configurado, agente offline, pasta inexistente ou caminho inválido."""


class DriveNotFound(DriveError):
    """O arquivo ou a pasta pedida não existe."""


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
    """Raiz do drive no modo local (`MODULE_DRIVE_ROOT`)."""
    if not settings.drive_root:
        raise DriveError("O drive não está configurado neste servidor (defina MODULE_DRIVE_ROOT).")
    root = Path(settings.drive_root)
    if not os.path.isdir(fs_path(root)):
        raise DriveError(f"A raiz do drive não existe ou não está acessível: {root}")
    return root


def _parts(relative: str) -> list[str]:
    rel = relative.replace("\\", "/").strip("/")
    if rel == "":
        return []
    parts = posixpath.normpath(rel).split("/")
    if relative.replace("\\", "/").startswith("/") or ":" in parts[0] or any(p in ("..", "") for p in parts):
        raise DriveError("Caminho inválido.")
    return parts


def safe_join(base: Path, relative: str) -> Path:
    """`base / relative`, garantindo que o resultado continua dentro de `base`."""
    return base.joinpath(*_parts(relative))


def join_rel(base: str, relative: str) -> str:
    """Junta dois caminhos relativos (posix) validando os dois — o resultado
    nunca sai de `base`. É a forma de montar "pasta do projeto + caminho
    pedido" para qualquer tipo de drive (local ou por agente)."""
    return "/".join(_parts(base) + _parts(relative))
