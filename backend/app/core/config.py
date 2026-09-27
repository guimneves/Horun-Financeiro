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


settings = Settings()
