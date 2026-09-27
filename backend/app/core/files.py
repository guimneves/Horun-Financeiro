"""Armazenamento de documentos em disco — caminho relativo salvo no banco
(`Document.storage_path`), arquivo de verdade num diretório que vira volume
Docker nomeado na hora do deploy (mesma disciplina do Postgres: nunca só
dentro do container). `MODULE_UPLOAD_ROOT` configurável por env, mesmo
padrão de `MODULE_DATABASE_URL` em core/config.py.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import settings

UPLOAD_ROOT = Path(settings.upload_root).resolve()


def save_upload(project_id: int, purchase_process_id: int, filename: str, content: bytes) -> tuple[str, int]:
    safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
    rel_dir = Path("projects") / str(project_id) / "purchases" / str(purchase_process_id)
    abs_dir = UPLOAD_ROOT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    (abs_dir / safe_name).write_bytes(content)
    rel_path = (rel_dir / safe_name).as_posix()
    return rel_path, len(content)


def resolve_path(storage_path: str) -> Path:
    return UPLOAD_ROOT / storage_path


def delete_file(storage_path: str) -> None:
    path = resolve_path(storage_path)
    if path.exists():
        path.unlink()
