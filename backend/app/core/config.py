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
    # Senha de coordenador inicial — só usada pra criar o registro de
    # configuração na primeira vez que o módulo sobe (bootstrap). Depois
    # disso, os coordenadores trocam pela própria interface e este valor
    # de env deixa de ter qualquer efeito.
    default_coordenador_password: str = os.environ.get(
        "MODULE_COORDENADOR_PASSWORD", "troque-esta-senha"
    )


settings = Settings()
