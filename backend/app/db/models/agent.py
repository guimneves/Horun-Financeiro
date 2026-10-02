"""Tabelas do Horun Agent (o programa instalado no PC onde o OneDrive está
sincronizado) — as MESMAS de todo módulo: vêm do pacote único do servidor do
agente (`app/agent_server/models.py`, cópia do Agent-Horun — não edite lá).
Só são usadas com `MODULE_DRIVE_MODE=agent`. Colunas novas do pacote entram
por `AGENT_MIGRATIONS` em `db/session.py`.
"""

from app.agent_server.models import AgentDevice, AgentEnrollCode, AgentTask  # noqa: F401
