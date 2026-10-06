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
    # Assina o token da sessão de coordenador (core/security.py). O
    # repositório é público: um valor padrão aqui seria uma chave conhecida
    # por todos, e qualquer um forjaria um token de coordenador. Por isso não
    # há padrão — fora do DEV_MODE o módulo não sobe sem ela (ver
    # check_production_settings).
    secret_key: str = os.environ.get("MODULE_SECRET_KEY", "")
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
    # Senha de coordenador inicial — só usada pra criar o registro de
    # configuração na primeira vez que o módulo sobe (bootstrap). Depois
    # disso, os coordenadores trocam pela própria interface e este valor
    # de env deixa de ter qualquer efeito. Sem ela (fora do DEV_MODE),
    # nenhuma senha é criada e o login de coordenador fica indisponível —
    # nunca um padrão público.
    default_coordenador_password: str = os.environ.get("MODULE_COORDENADOR_PASSWORD", "")
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
    # Gravar no drive (decisão de 06/10/2026): com "true", os documentos
    # anexados no módulo são copiados para a pasta do processo no drive e a
    # pasta "SEM NUMERO ..." passa a ter o nº quando ele é informado. Nunca
    # sobrescreve nem apaga. Padrão DESLIGADO: quem não ligar continua só
    # lendo (ex. a apresentação local, que aponta para o OneDrive real). No
    # modo agente, a pasta também precisa estar "read-write" no config.json
    # do Horun Agent.
    drive_write: bool = os.environ.get("MODULE_DRIVE_WRITE", "false").strip().lower() in ("1", "true", "yes", "sim")
    # Sincronização automática com o drive, nos dois sentidos, a cada N
    # minutos (services/drive_auto_sync.py). 0 = desligada.
    drive_auto_sync_minutes: int = int(os.environ.get("MODULE_DRIVE_AUTO_SYNC_MINUTES", "30"))
    # De quanto em quanto tempo o laço confere se está na hora (só uma
    # consulta ao banco; a sincronização em si segue o intervalo acima).
    drive_auto_sync_check_seconds: float = float(os.environ.get("MODULE_DRIVE_AUTO_SYNC_CHECK_SECONDS", "60"))


settings = Settings()


def drive_configured() -> bool:
    """O drive está ligado neste servidor (pasta local ou Horun Agent)?"""
    return settings.drive_mode == "agent" or bool(settings.drive_root)

MIN_SECRET_KEY_LENGTH = 32


def check_production_settings(dev_mode: bool) -> None:
    """Chamado na subida do módulo. Em produção, recusa iniciar com uma
    chave de assinatura ausente ou curta demais."""
    if dev_mode:
        return
    if len(settings.secret_key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"MODULE_SECRET_KEY ausente ou curta (mínimo {MIN_SECRET_KEY_LENGTH} caracteres). "
            'Gere uma com: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
