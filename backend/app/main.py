from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_auth,
    routes_budget,
    routes_categories,
    routes_known_users,
    routes_personnel,
    routes_projects,
    routes_purchases,
)
from app.core.identity import DEV_MODE
from app.core.known_users_middleware import KnownUsersMiddleware
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(title="Horun · Financeiro", version="0.1.0", lifespan=lifespan)

# Registra quem já apareceu numa requisição (ver core/known_users_middleware.py)
# — precisa vir antes do CORS na ordem de registro pra ficar na camada
# interna da pilha (CORS por fora, cobrindo toda resposta, inclusive erro).
app.add_middleware(KnownUsersMiddleware)

if DEV_MODE:
    # Só em desenvolvimento standalone: o frontend (Vite, porta 5173) e o
    # backend (porta 8000) são origens diferentes pro navegador. Em
    # produção, plugado no Core, tudo roda na mesma origem via gateway —
    # CORS não existe nem faz falta lá (Prompt_Horun_Modulo.md, seção 6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(routes_auth.router)
app.include_router(routes_projects.router)
app.include_router(routes_categories.router)
app.include_router(routes_budget.router)
app.include_router(routes_purchases.router)
app.include_router(routes_personnel.router)
app.include_router(routes_known_users.router)


@app.get("/health")
def health():
    # Sem autenticação — usado pelo Horun Core para o dashboard de status
    # (Prompt_Horun_Core.md, seção 5). Não expor aqui nada além do status.
    return {"status": "ok", "module": "financeiro"}
