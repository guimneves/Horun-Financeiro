from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_auth,
    routes_agent,
    routes_budget,
    routes_categories,
    routes_dashboard,
    routes_drive,
    routes_funding,
    routes_known_users,
    routes_personnel,
    routes_projects,
    routes_purchases,
)
from app.core.config import check_production_settings
from app.core.identity import DEV_MODE
from app.core.known_users_middleware import KnownUsersMiddleware
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if DEV_MODE:
        logging.getLogger("uvicorn.error").warning(
            "HORUN_DEV_MODE=true: toda requisição é tratada como o usuário 'admin', SEM login. "
            "Use só em desenvolvimento e nunca exponha esta porta na rede."
        )
    check_production_settings(DEV_MODE)
    create_db_and_tables()
    yield


app = FastAPI(title="Horun · Financeiro", version="0.1.0", lifespan=lifespan)

# Erro de validação (422) como UMA frase em português no `detail` — o padrão
# do FastAPI é uma lista de objetos em inglês, que o frontend (api/client.ts,
# que mostra `detail` direto) exibia como "[object Object]".
_VALIDATION_MESSAGES = {
    "greater_than_equal": "não pode ser negativo",
    "greater_than": "tem que ser maior que zero",
    "decimal_max_places": "aceita no máximo 2 casas decimais",
    "decimal_max_digits": "é grande demais",
    "decimal_parsing": "não é um número válido",
    "missing": "é obrigatório",
}
_FIELD_LABELS = {
    "quantity": "Quantidade",
    "estimated_unit_value": "Valor unitário",
    "unit_value": "Valor unitário",
    "planned_quantity": "Quantidade prevista",
    "monthly_rate": "Valor mensal",
    "final_value": "Valor final",
    "amount": "Valor",
    "title": "Título",
    "description": "Descrição",
}


@app.exception_handler(RequestValidationError)
async def _validation_error_pt(_request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err.get("loc") else "valor"
        label = _FIELD_LABELS.get(field, field)
        if err["type"] == "value_error":
            # nossos validadores (ex. reject_null) já falam português
            text = str(err.get("ctx", {}).get("error", err["msg"]))
        else:
            text = _VALIDATION_MESSAGES.get(err["type"], "é inválido")
        messages.append(f"{label}: {text}.")
    return JSONResponse(status_code=422, content={"detail": " ".join(messages) or "Dados inválidos."})

# Registra quem já apareceu numa requisição (ver core/known_users_middleware.py)
# — precisa vir antes do CORS na ordem de registro pra ficar na camada
# interna da pilha (CORS por fora, cobrindo toda resposta, inclusive erro).
app.add_middleware(KnownUsersMiddleware)

if DEV_MODE:
    # Só em desenvolvimento standalone: o frontend (Vite, porta 5173) e o
    # backend (porta 8000) são origens diferentes pro navegador. Em
    # produção, plugado no Core, tudo roda na mesma origem via gateway —
    # CORS não existe nem faz falta lá (Prompt_Horun_Modulo.md, seção 6).
    # Qualquer porta local: permite subir uma segunda cópia para teste ao
    # lado da que está aberta (frontend com VITE_API_URL apontando aqui).
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Toda a API vive sob /api: plugado no Core, o gateway só encaminha pro
# backend o que começa com `/m/financeiro/api/...` — o resto vai pro
# frontend (Prompt_Horun_Modulo.md, seção 6). Sem o prefixo, a SPA recebia
# index.html no lugar do JSON. `/health` fica fora, na raiz (contrato).
API_ROUTERS = (
    routes_auth.router,
    routes_projects.router,
    routes_categories.router,
    routes_budget.router,
    routes_purchases.router,
    routes_personnel.router,
    routes_funding.router,
    routes_dashboard.router,
    routes_drive.router,
    routes_known_users.router,
    routes_agent.router,
)
for _router in API_ROUTERS:
    app.include_router(_router, prefix="/api")


@app.get("/health")
def health():
    # Sem autenticação — usado pelo Horun Core para o dashboard de status
    # (Prompt_Horun_Core.md, seção 5). Não expor aqui nada além do status.
    return {"status": "ok", "module": "financeiro"}
