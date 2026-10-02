# Estado atual, decisões, plano e ideias — Horun · Financeiro

Documento de passagem de bastão. Escrito para quem retomar o projeto (inclusive
outra sessão do Claude Code em outra conta) sem acesso ao histórico da conversa.
Complementa o [`CHANGELOG.md`](CHANGELOG.md).

> **Repositório público.** Não commitar dados reais do projeto (valores em R$,
> nomes de pessoas ou fornecedores, planilhas, PDFs). Os testes usam estruturas
> sintéticas. As notas abaixo trazem só números estruturais.

## 1. Objetivo

Módulo **financeiro** do Projeto Horun: controle orçamentário e de compras de
projetos financiados (ex.: Petrobras/COPPETEC). O usuário (Guilherme M. Neves) **não
usa** a planilha nem os processos de compra no dia a dia: está replicando e
otimizando para outras pessoas. Pedido central: **"o programa deve fazer o mesmo
que a planilha, só que melhor"**, e **o software deve ler as pastas de cada item
no drive (OneDrive), inserir os itens usados lá e permitir consultá-los**.

Preferência registrada: **regras configuráveis ou justificáveis, não
restrições rígidas** ("restrições geram problemas de adaptabilidade").

## 2. Arquitetura

- **Backend** (`backend/`): FastAPI + SQLModel. SQLite em desenvolvimento,
  PostgreSQL em produção (`MODULE_DATABASE_URL`). Identidade vem de cabeçalhos
  injetados pelo Horun Core (`X-Horun-User-Id/User/Role`); `HORUN_DEV_MODE=true`
  usa um admin fixo.
- **Frontend** (`frontend/`): React + Vite + Tailwind, usa
  `@horun/design-system` (dependência `file:../../Horun Core/design-system`).
- **Permissões**: papel do Core só diz se é admin (criar projeto); dentro do
  módulo vale `ProjectMembership` (`coordenador` | `colaborador`).
- **Camadas do backend**: `api/` (rotas) → `services/` (regras: `balance`,
  `accrual`, `transitions`, `funding`, `audit`, `drive_scan`, `drive_sync`,
  `ledger`) → `db/models/`. `core/` tem config, identidade, permissões, arquivos
  e drive.
- **Orçamento**: `BudgetPosition` (identidade estável do item) × `BudgetItem`
  (valores numa `BudgetRevision`). Processos e atribuições apontam para a posição,
  nunca para a revisão.
- **Máquina de estados de compra** (`services/transitions.py`): verificação de
  orçamento → cotação → aguardando autorização → autorizado → nota fiscal →
  recebimento → concluído (+ rejeitado/cancelado). Único ponto de entrada.
- **Migrações**: padrão `_ensure_column` em `db/session.py` (igual ao Horun Core).

### Conceitos de saldo (regra vigente)

```
saldo = planejado + rendimentos − comprometido − realizado
comprometido = valor estimado dos processos ANTES da autorização
             + meses futuros comprometidos da Equipe Executora
realizado    = processos autorizados em diante (valor final se houver, senão estimado)
             + meses acumulados da Equipe Executora
meses (equipe) = meses de calendário, ignorando o dia, mês final incluído
```

## 3. Como rodar e testar

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
HORUN_DEV_MODE=true .venv/Scripts/uvicorn app.main:app --reload   # porta 8000
.venv/Scripts/python -m pytest -q                                   # suíte

# frontend
cd frontend && npm install && npm run dev                           # porta 5173
npx tsc -b && npx oxlint                                            # checagem
```

Para o drive (modo local): `MODULE_DRIVE_ROOT` = pasta que **contém** a pasta do
projeto; depois, em *Configurações*, `drive_folder` = nome da pasta do projeto.
Para ler a planilha: `pip install -e ".[import]"` (ou `[dev]`).

Nos testes `HORUN_DEV_MODE` fica desligado de propósito (precisam simular
usuários diferentes por cabeçalho).

## 4. Os dados reais (estrutura, sem valores)

Pasta do projeto no OneDrive (projeto 25465, "Maturação Artificial"):

- Pastas de categoria: `Equipamento e Material Permanente - Nacional/Importado`,
  `Material de consumo - Nacional/Importado`, `Serviço`, `Protótipo ou Unidade
  Piloto - Nacional/Importado`, `Obras e Instalações`, `Outros bens e direitos`,
  `Passagens`, `Diárias`, `Ajuda de custo`, `Equipe Executora`.
- Dentro: `Item N - descrição` → `AAAA-NNNN título` (processo; "(CANCELADO)" =
  tentativa cancelada) → PDFs.
- Pastas fora desse padrão: `1_Afastamento do País` (viagens com carta convite,
  cartão de embarque, hotel, passagem, relatório, seguro), `1_Reformulação do
  projeto No1/2/3`, `Documentos COPPETEC`, `Documentos SEI`, `Prestação de
  contas`, `Comodato de cilindros...`, `0_Saldo por item` (planilhas).
- Números: 94 pastas de item; **420 processos** (16 cancelados) em 7 categorias;
  **1.772 arquivos** (~99% PDF). Nomes de arquivo úteis: `autorizacao_de_fornecimento_*`
  (AF, ~300 processos), `NF`/`DANFE`/`nota`, `boleto`, `proposta`/`cotação`/
  `orçamento`, `pedido_importacao`; cotações costumam ser numeradas "1 - ", "2 - ",
  "3 - " e vir endereçadas à fundação.
- Caminhos passam de 260 caracteres (Windows precisa do prefixo `\\?\`).
- Planilha de acompanhamento (`0_Saldo por item/NOVA ... saldo_reformulação.xlsx`):
  abas `Quadro Resumo`, `Saldo por Item`, `Equipe Executora` e uma aba de
  lançamentos por categoria. **Layouts das abas de lançamentos diferem** (colunas
  deslocadas pela "Quantidade") — por isso o leitor acha colunas pelo cabeçalho.
  Há também `antiga.xlsx`, `antiga 2.xlsx`, `Calculo Pessoal.xlsx` (ainda **não
  analisadas**) e uma folha de pessoal dentro de `Equipe Executora`.
- A planilha tem inconsistências próprias (ex.: verificação com `#REF!`, soma
  de grupo que omite uma linha, uma fórmula de saldo que desconta rendimento de
  forma diferente das outras). Servem de argumento para o programa, mas a
  reconciliação deve saber que os números dela podem estar errados.
- Linhas da planilha com nº de processo inválido existem (ex.: "?", "xxxx", um
  ID de seguro) — o programa as lista com o valor.

## 5. Estado atual por branch

- **`master`**: estável. 96 testes do backend passam; frontend compila e passa
  no lint. Tem paridade com a planilha, correção da base e leitura de pastas
  (modo local). Ver CHANGELOG.
- **`wip/drive-agent`**: master + modo agente em andamento; **a suíte não importa**
  até terminar a religação (seção 7).
- Nada disso foi testado em produção; não há deploy.

## 6. Decisões já tomadas (não reabrir sem motivo)

1. **Meses da equipe**: regra da planilha (calendário, pago no mês seguinte).
2. **"Realizado"**: regra da planilha (nº de processo lançado = realizado).
3. **Saldo**: aceitou bloquear estouro, depois pediu flexibilidade → política por
   projeto (bloquear | avisar), padrão bloquear.
4. **Ordem do trabalho**: paridade → corrigir a base → leitura de pastas.
5. **Importação**: o programa lê pastas e a planilha por si só (não um CLI
   externo); começa lendo (plano sem gravar), só grava após confirmação.
6. **Não importar dados reais ainda** até o orçamento (SIGITEC + reformulações)
   estar cadastrado.
7. **Alembic não adotado**: manter `_ensure_column` como o Horun Core; decidir
   junto com o Core se migra.
8. **Bifurcação do trabalho do agente**: uma sessão trabalha no Financeiro, outra
   no repositório **Horun Agent**. O contrato entre as duas está em
   [`AGENT_CONTRACT.md`](AGENT_CONTRACT.md).

## 7. Modo agente — divisão de trabalho e o que falta

### Contexto
O OneDrive está sincronizado num PC; o backend vai rodar em Docker (provavelmente
no servidor do laboratório). O backend só lê a pasta como caminho local; no modo
agente, o **Horun Agent** (já existe em `Programas/Horun Agent`, com a ponte do
lado servidor no RE7S) lê por ele. O agente consulta o servidor (nunca o
contrário), então o PC não abre porta.

### Lado do agente — FEITO (Agent-Horun 0.4.0, 2026-10-02)
O servidor do agente agora é o pacote único (`backend/app/agent_server/`, o
mesmo do RE7S). Diferenças em relação ao pedido original no topo do
`AGENT_CONTRACT.md` (campos em `args`, versões 0.3/0.4, porta estreita em vez
de liberar o gateway). Texto original do pedido, para referência:
`list_tree` (pastas+tamanhos), `read_file` com `offset/length` e `size`, campo
`code` nos erros, roots somente leitura, **caminhos > 260 no Windows**, cabeçalho
`X-Horun-Agent-Version: 0.2` (obrigatório) e `Task` tolerante a campos extras.
Há um prompt pronto no fim do contrato.

### Lado do Financeiro (esta sessão) — o que falta na `wip/drive-agent`
1. **Religar o que importa funções removidas de `core/drive.py`**:
   - `api/routes_drive.py`: trocar `project_drive_dir`/`safe_join`/`fs_path`
     por `get_drive_backend()` + `join_rel(project.drive_folder, ...)`. `scan`/`sync`:
     `backend.list_tree(folder)` → `scan_entries`; planilha:
     `backend.read_bytes(join_rel(folder, ledger_path))`; `browse`:
     `list_tree(..., recursive=False)`; `file`: `serve_file`. Mapear `DriveNotFound`
     → 404 e `DriveError` → 409. `status`: modo agente = `agent_state().online`;
     adicionar `mode` ao schema.
   - `api/routes_projects.py`: validar `drive_folder` com `join_rel` (sintaxe) e,
     só no modo local, checar existência com `LocalDrive.list_tree`.
   - `core/files.py` e `api/routes_purchases.py`: o download de documento
     "drive" passa a usar `serve_file(join_rel(project.drive_folder, doc.storage_path), ...)`;
     tirar `resolve_document_path`.
2. **`services/drive_scan.py`**: criar `scan_entries(entries, base)` que monta a
   árvore a partir da lista plana (`DriveEntry`) e reproduz a lógica atual;
   manter `scan_project_folder(path)` como wrapper sobre `LocalDrive`.
   Cuidado com a ordem dos arquivos (arquivos da pasta antes das subpastas, sem
   diferenciar maiúsculas) e com pastas de processo vazias (só vêm como entrada
   de pasta).
3. **`services/ledger.py`**: `read_ledger(bytes)` usando `io.BytesIO` (hoje lê de
   caminho).
4. **`main.py`**: incluir `routes_agent.router`.
5. **Frontend**: `DriveStatus` ganha `mode`; mostrar "agente offline" e o
   estado do agente; opcionalmente tela admin de dispositivos/código de
   enrolamento.
6. **Testes**: um **agente falso** em thread (consulta `/agent/tasks` e executa
   `list_tree`/`read_file` sobre uma pasta temporária) para rodar os mesmos testes
   de `test_drive.py` em modo agente; casos: agente offline (falha rápida), agente
   antigo (sem versão → não recebe campos novos nem `list_tree`), tarefa expirada,
   arquivo acima do limite, leitura em pedaços, token revogado.
7. **Docker/compose**: variáveis `MODULE_DRIVE_MODE=agent`, root e timeout;
   **porta estreita do agente** (8002, nginx como o do RE7S — ver
   `AGENT_CONTRACT.md`, "Rede").
8. ~~Core liberar `/m/financeiro/agent/*`~~ — não precisa: porta estreita.
9. ~~Extrair o lado servidor do agente~~ — FEITO: pacote único, já ligado aqui
   (`routes_agent` no `main.py`, migrações em `AGENT_MIGRATIONS`). Para
   atualizar: `python scripts/vendor_server.py "<Financeiro>/backend"` no
   Agent-Horun.

### Consequências aceitas do modo agente
Latência de um intervalo de consulta por ação; sem o PC ligado não se lista nem
baixa arquivo (processos/documentos já cadastrados continuam consultáveis); um
mesmo agente pode atender vários módulos no mesmo PC (`servers` no
`config.json`, desde 0.3.0).

## 8. Pendências e decisões em aberto

- **Onde o backend vai rodar** e **em qual máquina o OneDrive está sincronizado**
  (pergunta feita, ainda sem resposta). Define local × agente.
- **Cadastrar o orçamento** do projeto (SIGITEC + reformulações 1–3) a partir da
  planilha ("Saldo por Item") ou pela tela de revisões — **pré-requisito** para a
  importação real (os processos se ligam aos itens do orçamento).
- **Estados dos processos importados** são inferência pelos arquivos; a maioria
  fica "nota fiscal emitida" (só 2 "concluído"). O saldo fica correto; os estados
  precisam de conferência. Aceitar assim ou definir outra regra?
- **12 processos com pasta e sem valor na planilha** entram com valor zero.
- **Linhas inválidas da planilha** (valor não importado) — decidir caso a caso.
- Nota fiscal acima do estimado e Equipe Executora: **não bloqueiam** — confirmar.
- `MAX_QUOTES_PER_PROCESS = 3` é um **máximo**; se a regra da fundação é um
  **mínimo** de 3 cotações, o modelo está invertido — confirmar.
- Equipe Executora: importação de pessoal a partir das planilhas/pastas ainda não
  feita.
- Alembic × `_ensure_column` (decidir com o Core).

## 9. Plano (ordem sugerida)

1. Terminar o modo agente (seção 7) em paralelo ao trabalho no repositório do agente.
2. Cadastrar o orçamento real → rodar "Ler pastas" com a planilha → conferir o
   plano → sincronizar → corrigir estados na tela.
3. **Fluxos por categoria** (hoje há um fluxo único, o de compra): Afastamento do
   País (carta convite, cartão de embarque, hotel, passagem, relatório, seguro),
   Diárias/Ajuda de custo, Serviço, Prestação de contas — cada um com seus
   documentos e estados.
4. **Documentos de projeto** (Documentos COPPETEC, SEI, reformulações, Comodato):
   hoje documento só se liga a processo de compra ou atribuição de pessoal.
5. Importação da **Equipe Executora** (pessoal) e comparação com a planilha de cálculo.
6. Endurecer: concorrência (versão otimista), paginação, fuso de `date.today()`,
   revisão do uso de `MODULE_SECRET_KEY` (hoje sem uso).
7. Docker/compose de produção e integração com o Core.

## 10. Ideias discutidas (backlog completo)

Implementadas: ver CHANGELOG. Discutidas e **não** feitas:

- **Fluxos por categoria** e **documentos de projeto** (itens 3–4 acima).
- **Moeda estrangeira/câmbio** para categorias importadas (hoje só uma nota de
  texto): campos de moeda, valor original, taxa e data.
- **Ligar tentativas**: pasta "(CANCELADO)" ao irmão com mesmo título
  (`previous_attempt_id`) — heurística de título; não implementada por risco.
- **Alternativas de armazenamento para servidor Linux** (descartadas em favor do
  agente, mas válidas): pasta montada por SMB; `rclone` espelhando o OneDrive;
  integração direta com a API do OneDrive (Microsoft Graph).
- **Aviso do OneDrive "Files On-Demand"**: ler arquivo só-nuvem o baixa; em Docker
  no Windows pode falhar — marcar a pasta "manter sempre neste dispositivo".
- **Camada de armazenamento abstrata** com pasta legível por humanos (já feita
  para leitura via `DriveBackend` no WIP; escrita de volta no drive foi
  deliberadamente **descartada**: o módulo só lê).
- **Importador como tela vs. CLI**: foi escolhida a tela no próprio programa.
- **Substituir Alembic**: ver decisão 7.
- Cache de PDFs buscados pelo agente (acelera consulta, custa espaço).
- Tela de administração de agentes (código de enrolamento, dispositivos,
  revogação, versão, último sinal).
- Documento de `Prompt_Importacao_Financeiro.md` (já no repositório) descreve o
  fluxo de importação por agente de IA; o importador do programa o complementa.

### Crítica do programa original — situação

Resolvidos nesta sessão: ausência de histórico; nº de processo solto; upload sem
limite/hash; migrações caseiras sem teste; filtro em Python; nenhuma checagem de
saldo; falta de parcelas/quantidade disponível; arquivo do drive apagável;
testes poluindo o projeto.

**Em aberto**: fluxo único para todas as categorias; só 6→9 tipos de documento e
sem documentos de projeto; sem câmbio; concorrência sem controle; sem paginação;
`date.today()` no fuso do servidor; `secret_key` sem uso.

## 11. Como retomar em outra sessão/conta

1. `git clone https://github.com/guimneves/Horun-Financeiro` e
   `git switch wip/drive-agent` (para continuar o modo agente) ou fique em `master`.
2. Ler, nesta ordem: `CLAUDE.md`, este arquivo, `CHANGELOG.md`, `AGENT_CONTRACT.md`.
3. Instalar e rodar a suíte (seção 3). Na `master` deve dar **96 passed**.
4. As memórias da sessão original ficam fora do repositório (no perfil do
   Claude Code da conta antiga); o essencial delas está na seção 1 e 6 acima.
5. Contexto externo: `Programas/Horun Core` (design-system e plataforma),
   `Programas/Horun Agent` (agente), `Projeto Horun/Rock Eval Horun Dev` (RE7S:
   referência do padrão de agente e de módulo).
