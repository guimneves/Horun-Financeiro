# Horun · Financeiro

Módulo do **Projeto Horun**. Gerado a partir do template padrão — ver `../Prompt_Horun_Core.md` (arquitetura da plataforma) e `../Prompt_Horun_Modulo.md` (contrato completo de módulo).

## Estrutura

```
backend/    API FastAPI + SQLModel, própria deste módulo
frontend/   React + Vite + Tailwind, usa @horun/design-system para tema/identidade visual
MODULE.md   Manifesto lido pelo Horun Core (nome, ícone, porta, health check)
```

## Desenvolvendo de forma independente (sem o Horun Core rodando)

```
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
set HORUN_DEV_MODE=true
uvicorn app.main:app --reload

# frontend (outro terminal)
cd frontend
npm install
npm run dev
```

Com `HORUN_DEV_MODE=true`, o backend usa um usuário fixo (admin de desenvolvimento) em vez de exigir os cabeçalhos de identidade que só o Core injeta em produção — dá pra desenvolver e testar o módulo inteiro isolado.

## Plugando no Horun (quando estiver pronto)

1. Remover `HORUN_DEV_MODE` do ambiente de produção — o backend passa a exigir identidade vinda do Core.
2. Adicionar o serviço deste módulo ao `docker-compose.yml` do servidor (backend sem porta exposta ao host — só alcançável pelo Core, mesma regra do RE7S).
3. Core lê `MODULE.md` e cadastra o módulo no dashboard automaticamente.
