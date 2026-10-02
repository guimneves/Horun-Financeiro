"""Acesso de LEITURA ao drive, atrás de uma interface — o resto do módulo
(leitura de pastas, navegação, download, planilha de valores) não sabe se o
drive é uma pasta do próprio servidor ou se está num PC distante, alcançado
pelo Horun Agent. Escolhido por `MODULE_DRIVE_MODE` ("local" | "agent").

Todos os caminhos são relativos à RAIZ do drive, em posix. A pasta de cada
projeto é só um prefixo (`Project.drive_folder`), aplicado com `join_rel`.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from fastapi import Response

from app.core.config import settings
from app.core.drive import DriveError, DriveNotFound, drive_root, fs_path, join_rel, safe_join


@dataclass(frozen=True)
class DriveEntry:
    path: str  # relativo à raiz do drive, posix
    is_dir: bool
    size: int | None  # None para pastas


class DriveBackend(ABC):
    mode: str

    @abstractmethod
    def list_tree(self, path: str, *, recursive: bool = True) -> list[DriveEntry]:
        """Pastas e arquivos SOB `path` (sem incluí-la), ordenados por caminho."""

    @abstractmethod
    def read_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        """Conteúdo do arquivo. `DriveNotFound` se não existir."""

    def local_path(self, path: str) -> str | None:
        """Caminho no disco do servidor, se o arquivo estiver nele (permite
        servir sem carregar na memória). Nulo para drive remoto."""
        return None


class LocalDrive(DriveBackend):
    mode = "local"

    def __init__(self, root: Path):
        self.root = root

    def list_tree(self, path: str, *, recursive: bool = True) -> list[DriveEntry]:
        base = safe_join(self.root, path)
        if not os.path.isdir(fs_path(base)):
            raise DriveNotFound(f"Pasta não encontrada no drive: {path or '(raiz)'}")
        root_plain = os.path.abspath(self.root)
        entries: list[DriveEntry] = []

        def rel(plain: str) -> str:
            return os.path.relpath(plain, root_plain).replace("\\", "/")

        if not recursive:
            with os.scandir(fs_path(base)) as it:
                for e in it:
                    full = os.path.join(os.path.abspath(base), e.name)
                    entries.append(
                        DriveEntry(rel(full), e.is_dir(), None if e.is_dir() else e.stat().st_size)
                    )
        else:
            for current, dirs, files in os.walk(fs_path(base)):
                plain = current[4:] if current.startswith("\\\\?\\") else current
                for name in dirs:
                    entries.append(DriveEntry(rel(os.path.join(plain, name)), True, None))
                for name in files:
                    full = os.path.join(plain, name)
                    entries.append(DriveEntry(rel(full), False, os.stat(fs_path(full)).st_size))
        return sorted(entries, key=lambda e: e.path)

    def read_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        target = fs_path(safe_join(self.root, path))
        if not os.path.isfile(target):
            raise DriveNotFound(f"Arquivo não encontrado no drive: {path}")
        if max_bytes is not None and os.path.getsize(target) > max_bytes:
            raise DriveError(f"Arquivo acima do limite de {max_bytes / 1024 / 1024:.0f} MB.")
        with open(target, "rb") as handle:
            return handle.read()

    def local_path(self, path: str) -> str | None:
        target = fs_path(safe_join(self.root, path))
        return target if os.path.isfile(target) else None


AGENT_OFFLINE_MESSAGE = (
    "O agente do drive está offline — confira se o PC com o OneDrive está ligado, "
    "com rede e com o Horun Agent rodando."
)


def _agent_error(exc: Exception) -> DriveError:
    from app.services import agent_bridge

    if isinstance(exc, agent_bridge.AgentOfflineError):
        return DriveError(AGENT_OFFLINE_MESSAGE)
    return DriveError(str(exc))


class AgentDrive(DriveBackend):
    """Drive alcançado pelo Horun Agent (ver services/agent_bridge.py)."""

    mode = "agent"

    def __init__(self, root_name: str):
        self.root_name = root_name

    def list_tree(self, path: str, *, recursive: bool = True) -> list[DriveEntry]:
        from app.services import agent_bridge

        try:
            entries = agent_bridge.list_tree(self.root_name, join_rel("", path), recursive=recursive)
        except agent_bridge.AgentTaskError as exc:
            if agent_bridge.file_not_found(exc):
                raise DriveNotFound(f"Pasta não encontrada no drive: {path or '(raiz)'}") from exc
            raise _agent_error(exc) from exc
        return sorted((DriveEntry(e.path, e.is_dir, e.size) for e in entries), key=lambda e: e.path)

    def read_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        from app.services import agent_bridge

        try:
            return agent_bridge.read_bytes(self.root_name, join_rel("", path), max_bytes=max_bytes)
        except agent_bridge.AgentTaskError as exc:
            if agent_bridge.file_not_found(exc):
                raise DriveNotFound(f"Arquivo não encontrado no drive: {path}") from exc
            raise _agent_error(exc) from exc


def get_drive_backend() -> DriveBackend:
    if settings.drive_mode == "agent":
        return AgentDrive(settings.drive_agent_root)
    return LocalDrive(drive_root())


def serve_file(path: str, filename: str, media_type: str | None, *, inline: bool = False) -> Response:
    """Resposta de um arquivo do drive — direto do disco quando o drive é
    local, ou buscado pelo agente (em memória, com limite de tamanho).
    `inline`: exibir na página em vez de baixar, só para os tipos de
    `PREVIEWABLE_TYPES` (core/files.py)."""
    from urllib.parse import quote

    from app.core.files import PREVIEWABLE_TYPES, file_response

    backend = get_drive_backend()
    local = backend.local_path(path)
    if local is not None:
        return file_response(local, filename, media_type, inline=inline)
    data = backend.read_bytes(path, max_bytes=settings.agent_max_file_bytes)
    media_type = (media_type or "application/octet-stream").split(";")[0].strip().lower()
    disposition = "inline" if inline and media_type in PREVIEWABLE_TYPES else "attachment"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
