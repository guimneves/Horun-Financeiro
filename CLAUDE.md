# Horun · Financeiro — guia para o Claude Code

Módulo financeiro do Projeto Horun (orçamento, compras e equipe de projetos
financiados). Backend FastAPI+SQLModel (`backend/`), frontend React+Vite (`frontend/`).

**Leia primeiro:** `docs/ESTADO_E_PLANOS.md` (estado, decisões, plano, ideias) e
`docs/CHANGELOG.md`. Contrato do agente do drive: `docs/AGENT_CONTRACT.md`.

## Regras do projeto

- **Repositório público: nunca commitar dados reais** (valores, nomes de pessoas
  ou fornecedores, planilhas, PDFs, bancos `.db`). Testes usam estruturas sintéticas.
- **O módulo só LÊ o drive.** Nunca copiar, mover, escrever ou apagar arquivos nele.
  Documento do tipo "drive" apenas aponta para o arquivo.
- Comentários, mensagens de erro e textos de interface em **português**; nomes de
  código em inglês, como já está.
- **A planilha de acompanhamento é a referência de regra** (meses de calendário
  pagos no mês seguinte; realizado = nº de processo lançado), mas o programa deve
  fazer "o mesmo, só que melhor".
- **Preferir regras configuráveis ou justificáveis a restrições rígidas** (política
  de saldo por projeto; requisito de documento dispensável com justificativa).
- Mudança de esquema: novo campo em modelo com tabela existente → somar
  `_ensure_column` em `backend/app/db/session.py` **no mesmo commit** (padrão do
  Horun Core; Alembic não é usado).
- Valores monetários: `Decimal` / `Numeric(14,2)`, nunca float.
- Caminhos do drive passam por `core/drive.py` (`join_rel`/`safe_join`/`fs_path`);
  no Windows os caminhos reais passam de 260 caracteres.

## Comandos

```bash
cd backend && .venv/Scripts/python -m pytest -q        # master: 96 passam
cd frontend && npx tsc -b && npx oxlint
```

Testes não usam `HORUN_DEV_MODE` (simulam usuários por cabeçalho) e gravam uploads
numa pasta temporária.

## Estado

Ver seção 5 de `docs/ESTADO_E_PLANOS.md`. `master` = estável; `wip/drive-agent` =
modo agente em andamento (a suíte não importa lá até religar as rotas; passos na
seção 7).
