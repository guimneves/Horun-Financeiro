# Horun · Financeiro — guia para o Claude Code

Módulo financeiro do Projeto Horun (orçamento, compras e equipe de projetos
financiados). Backend FastAPI+SQLModel (`backend/`), frontend React+Vite (`frontend/`).

**Leia primeiro:** `docs/ESTADO_E_PLANOS.md` (estado, decisões, plano, ideias) e
`docs/CHANGELOG.md`. Contrato do agente do drive: `docs/AGENT_CONTRACT.md`.

## Regras do projeto

- **Repositório público: nunca commitar dados reais** (valores, nomes de pessoas
  ou fornecedores, planilhas, PDFs, bancos `.db`). Testes usam estruturas sintéticas.
- **Drive: lê sempre; escreve só arquivos novos, e só com `MODULE_DRIVE_WRITE=true`**
  (decisão de 06/10/2026, `services/drive_write.py`). NUNCA sobrescreve (nome
  ocupado vira "nome (2).pdf") e NUNCA apaga — remover/desvincular documento no
  módulo não toca no drive. A única movimentação: os arquivos da pasta "SEM NUMERO
  ..." de um processo passam para "AAAA-N título" quando o nº é informado.
  Documento do tipo "drive" apenas aponta para o arquivo. Testes só em pastas
  temporárias — nunca a pasta real do OneDrive nem `C:\HorunDemo`.
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
- Valores monetários: `Decimal` / `Numeric(14,2)`, nunca float. Na entrada da API,
  usar os tipos de `app/core/money.py` (`Money`, `PositiveQuantity`...) e
  `round_money` em todo valor calculado; campo obrigatório em PATCH ganha
  `reject_null`.
- Toda rota da API fica sob `/api` (prefixo aplicado em `main.py`) — é o que o
  gateway do Core usa para separar API de estáticos.
- Caminhos do drive passam por `core/drive.py` (`join_rel`/`safe_join`/`fs_path`);
  no Windows os caminhos reais passam de 260 caracteres.

## Comandos

```bash
cd backend && .venv/Scripts/python -m pytest -q        # master: 279 passam
cd frontend && npx tsc -b && npx oxlint
```

Testes não usam `HORUN_DEV_MODE` (simulam usuários por cabeçalho, como atrás do
Core) e gravam uploads numa pasta temporária. O esquema de desenvolvimento
(membros + senha mestra) é testado com o fixture `dev_mode` (`tests/conftest.py`).

**Papéis** (decisão de 06/10/2026, `core/permissions.py`): atrás do Core o papel
vem do cargo no Horun (`X-Horun-Level` 1–2 = coordenador em todo projeto; demais =
colaborador); `ProjectMembership` só define quem recebe os avisos. Membros que dão
acesso e senha mestra: só com `HORUN_DEV_MODE=true`.

## Estado

Ver seção 5 de `docs/ESTADO_E_PLANOS.md`. Desde 06/10/2026 o modo agente do
drive está na `master` (a `wip/drive-agent` foi incorporada): o mesmo código roda
no servidor com `MODULE_DRIVE_MODE=agent` (`docker-compose.yml`, guia em
`docs/DEPLOY.md`) e localmente com `MODULE_DRIVE_MODE=local`
(`Apresentar_Financeiro.bat`; `docker-compose.dev.yml` para o standalone em
Docker). Pendências e próximos passos: seções 8 e 9.
