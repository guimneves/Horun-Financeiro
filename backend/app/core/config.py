"""Configuração deste módulo, lida de variáveis de ambiente — mesmo padrão
do RE7S (ver Rock Eval Horun Dev/backend/app/core/config.py). Em produção,
atrás do Horun Core, MODULE_DATABASE_URL aponta para o PostgreSQL do
servidor; em desenvolvimento standalone, o padrão abaixo já basta.
"""

from __future__ import annotations

import os


class Settings:
    database_url: str = os.environ.get(
        "MODULE_DATABASE_URL", "sqlite:///./financeiro_dev.db"
    )
    secret_key: str = os.environ.get("MODULE_SECRET_KEY", "dev-only-troque-em-producao")
    # Diretório dos documentos anexados (cotações, notas fiscais, etc.) —
    # vira volume Docker nomeado em produção, mesma disciplina do Postgres.
    upload_root: str = os.environ.get("MODULE_UPLOAD_ROOT", "./uploads")
    # Limite por arquivo enviado pela API (MB). Arquivos que já estão no
    # drive (sincronização de pastas) não passam por aqui.
    max_upload_mb: int = int(os.environ.get("MODULE_MAX_UPLOAD_MB", "50"))
    # Raiz do drive do Financeiro (a pasta do OneDrive que contém a pasta de
    # cada projeto). Cada projeto guarda só o caminho RELATIVO a esta raiz
    # (`Project.drive_folder`) — assim o mesmo cadastro vale no PC de casa,
    # neste PC e no servidor, cada um com a sua raiz. Vazio = recurso desligado.
    drive_root: str | None = os.environ.get("MODULE_DRIVE_ROOT") or None
    # Como o backend alcança o drive: "local" lê a pasta direto do disco
    # (MODULE_DRIVE_ROOT); "agent" pede ao Horun Agent, instalado no PC onde o
    # OneDrive está sincronizado, que leia por ele (ver docs/AGENT_CONTRACT.md).
    drive_mode: str = os.environ.get("MODULE_DRIVE_MODE", "local").lower()
    # Nome lógico da pasta liberada no config.json do agente (o servidor nunca
    # sabe o caminho real do disco).
    drive_agent_root: str = os.environ.get("MODULE_DRIVE_AGENT_ROOT", "financeiro")
    # Quanto o backend espera o agente responder a UMA tarefa, e o tamanho de
    # cada pedaço de arquivo pedido. O agente consulta a cada poucos segundos,
    # então o prazo precisa ser bem maior que o intervalo dele.
    agent_task_timeout_seconds: float = float(os.environ.get("MODULE_AGENT_TASK_TIMEOUT", "30"))
    agent_chunk_bytes: int = int(os.environ.get("MODULE_AGENT_CHUNK_MB", "4")) * 1024 * 1024
    # Maior arquivo que o backend aceita buscar pelo agente (planilha, PDF).
    agent_max_file_bytes: int = int(os.environ.get("MODULE_AGENT_MAX_FILE_MB", "50")) * 1024 * 1024


settings = Settings()
