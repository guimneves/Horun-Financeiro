"""Armazenamento de documentos. Há dois tipos (`Document.storage_kind`):

- "upload": enviado pela API e guardado em disco, num diretório que vira
  volume Docker nomeado na hora do deploy (mesma disciplina do Postgres: nunca
  só dentro do container). Caminho relativo salvo no banco
  (`Document.storage_path`); `MODULE_UPLOAD_ROOT` configurável por env, mesmo
  padrão de `MODULE_DATABASE_URL` em core/config.py.
- "drive": o arquivo já existe na pasta do projeto no drive e o módulo só
  aponta para ele. Nunca é copiado nem apagado por aqui.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.drive import fs_path, project_drive_dir, safe_join
from app.db.models.document import Document
from app.db.models.project import Project

UPLOAD_ROOT = Path(settings.upload_root).resolve()


async def read_upload_limited(file: UploadFile) -> tuple[bytes, str]:
    """Lê o upload em pedaços, recusando acima do limite (sem carregar um
    arquivo gigante inteiro na memória) e calculando o hash."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Arquivo acima do limite de {settings.max_upload_mb} MB.",
            )
        digest.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), digest.hexdigest()


def save_upload(project_id: int, owner_kind: str, owner_id: int, filename: str, content: bytes) -> tuple[str, int]:
    """`owner_kind` separa o namespace de armazenamento por tipo de dono
    (ex. "purchases", "personnel") — sem isso, um PurchaseProcess e um
    PersonnelAssignment com o mesmo id numérico no mesmo projeto cairiam no
    mesmo diretório."""
    safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
    rel_dir = Path("projects") / str(project_id) / owner_kind / str(owner_id)
    abs_dir = UPLOAD_ROOT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    (abs_dir / safe_name).write_bytes(content)
    rel_path = (rel_dir / safe_name).as_posix()
    return rel_path, len(content)


def resolve_path(storage_path: str) -> Path:
    return UPLOAD_ROOT / storage_path


def resolve_document_path(project: Project, doc: Document) -> str:
    """Caminho no disco do arquivo de um documento, pronto para abrir (já com
    o prefixo de caminho longo no Windows). Levanta `DriveError` se o drive não
    estiver acessível (só para documentos do tipo "drive")."""
    if doc.storage_kind == "drive":
        return fs_path(safe_join(project_drive_dir(project), doc.storage_path))
    return fs_path(resolve_path(doc.storage_path))


def delete_file(storage_path: str) -> None:
    """Apaga um arquivo ENVIADO pela API. Nunca chamar para documento do drive."""
    path = resolve_path(storage_path)
    if path.exists():
        path.unlink()


# Tipos que podem ser EXIBIDOS na página (leitor do navegador) em vez de
# baixados — pedido do usuário: ler os PDFs sem baixar. Lista fechada de
# propósito: um HTML ou SVG aberto dentro do Horun rodaria script com a
# sessão de quem abriu; esses continuam sempre como download.
PREVIEWABLE_TYPES = frozenset({
    "application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "text/plain",
})


def file_response(path: str | os.PathLike[str], filename: str, media_type: str | None, *, inline: bool = False) -> FileResponse:
    """Resposta de arquivo: download (padrão) ou exibição na página, se
    `inline` e o tipo estiver em `PREVIEWABLE_TYPES`."""
    media_type = (media_type or "application/octet-stream").split(";")[0].strip().lower()
    show = inline and media_type in PREVIEWABLE_TYPES
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if show else "attachment",
        # o navegador nunca "adivinha" outro tipo (ex. tratar como HTML)
        headers={"X-Content-Type-Options": "nosniff"},
    )
