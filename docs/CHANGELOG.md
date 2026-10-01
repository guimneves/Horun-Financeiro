# Changelog — Horun · Financeiro

Registro do que mudou desde o último commit do repositório
(`98ea7d4 — Correcoes da revisao de codigo: 10 achados confirmados`), na
sessão de trabalho iniciada em 29/09/2026. Para o estado atual, decisões e
plano, ver [`ESTADO_E_PLANOS.md`](ESTADO_E_PLANOS.md).

Duas branches carregam este trabalho:

| Branch | O que tem | Testes |
|---|---|---|
| `master` | Tudo abaixo **exceto** o modo agente do drive. É o estado estável. | 96 testes do backend passam; frontend compila (`tsc -b`) e passa no lint |
| `wip/drive-agent` | `master` + o trabalho **em andamento** do modo agente (ver "Em andamento"). **A suíte não importa** nesta branch até terminar a religação das rotas. | — |

---

## Em `master` (estável)

### Regras de negócio — alinhadas à planilha de acompanhamento de saldo

Decididas pelo usuário ("vale sempre a regra da planilha"):

- **Meses da Equipe Executora** (`services/accrual.py`): passam a ser **meses de
  calendário, ignorando o dia, com o mês final incluído** (a planilha paga no
  mês seguinte ao trabalhado). Ex.: 01/05/2024 até 01/10/2026 = 30 meses (a regra
  antiga, aniversário + dias/30, dava 29). Não existe mais mês fracionado.
  Mantida uma extensão do programa: atribuição ativa com data de fim futura gera
  "comprometido" pelos meses que faltam.
- **"Realizado"** (`services/balance.py`, `db/models/purchase.py`): passa a ser o
  processo **autorizado em diante** (autorizado, nota fiscal, recebimento,
  concluído), pelo valor final quando existe, senão o estimado — como a planilha,
  que lança a linha assim que há nº de processo COPPETEC. Antes da autorização o
  valor é só "comprometido" (coluna que a planilha não tem). Antes, realizado era
  só processo `concluido` com valor final.

### Flexibilidade (pedido: "não quero travar demais")

- **Política de saldo por projeto** (`Project.balance_policy`): `bloquear`
  (recusa criar/aumentar processo acima do saldo, HTTP 409 com mensagem pronta:
  disponível, solicitado, quanto falta) ou `avisar` (deixa passar; o aviso volta
  em `warnings` na resposta). Padrão `bloquear`. Processos vindos do drive nunca
  são bloqueados.
- **Requisito de documento dispensável**: o coordenador pode avançar um processo
  sem o documento exigido informando `override_reason`; a justificativa fica no
  histórico. Colaborador não pode; estado errado continua recusado.
- Não bloqueado de propósito: nota fiscal acima do estimado (fato consumado) e
  Equipe Executora (acumula com o tempo).

### Paridade com a planilha

- **Quantidade disponível** por item (`available_quantity` em `/balance`):
  quantidade prevista menos a lançada em processos comprometidos/realizados;
  nulo na Equipe Executora.
- **Parcelas de repasse** (`FundingInstallment`) e **% utilizado** por parcela,
  com a regra da linha "% Utilizado" do Quadro Resumo (1ª: realizado ÷ valor, no
  máx. 100%; demais só aparecem quando o realizado já cobriu o acumulado
  anterior).
- **Resumo do projeto** (`GET /projects/{id}/overview`): totais por grupo
  (capital/corrente), total do projeto, parcelas com % utilizado e contagem de
  itens com saldo negativo. Os "ok/verificar" da planilha **não** foram
  replicados (seriam sempre "ok" por construção do cálculo).

### Correção da base

- **Histórico de eventos** (`AuditEvent`, `services/audit.py`,
  `GET /projects/{id}/events`): quem fez o quê e quando — criação, edição,
  transições (de/para, motivo, requisito dispensado), documentos
  enviados/removidos/reclassificados, sincronização com o drive, troca de parcelas.
- **Nº de processo COPPETEC normalizado e único por projeto**
  (`core/process_number.py`): "2024 3708", "2024-3708" e "2024_3708" viram
  `2024-3708`. Índice único `(project_id, process_number)`; conflito = 409 com
  mensagem clara (inclusive em `autorizar`).
- **Upload**: limite de tamanho (`MODULE_MAX_UPLOAD_MB`, padrão 50) com leitura
  em pedaços (413 acima do limite) e `sha256` do conteúdo guardado e registrado
  no histórico.
- **Migração de bancos antigos** (`db/session.py`): novas colunas via
  `_ensure_column` e índice único com `CREATE UNIQUE INDEX IF NOT EXISTS`;
  duplicados num banco antigo não impedem a subida (apenas log). Testado contra
  um banco no esquema antigo. (Alembic **não** foi adotado — ver decisões.)
- Filtro por categoria em `list_processes` feito na consulta SQL (antes em Python).
- Documento do tipo "drive" **nunca** é apagado do disco ao ser removido
  (só desfaz o vínculo).
- Novo tipo de documento: reclassificar (`PATCH .../documents/{id}`), mesmo em
  processo encerrado (só metadado, fica no histórico).
- Tipos de documento novos: `autorizacao_fornecimento`, `boleto`,
  `pedido_importacao`.
- Testes passaram a usar pasta temporária para uploads (antes criavam
  `backend/uploads/` dentro do projeto, o que quebrava `pip install -e .`).
- `pyproject.toml`: `[tool.setuptools.packages.find] include = ["app*"]` e extra
  opcional `import` (`openpyxl`, também em `dev`).

### Drive do Financeiro — ler as pastas e a planilha

Resolve "o software lê as pastas de cada item, insere os itens usados e permite
consultá-los":

- **Configuração**: `MODULE_DRIVE_ROOT` (pasta que contém a pasta de cada
  projeto) e `Project.drive_folder` (relativa a ela). Nada é copiado: o
  documento (`storage_kind="drive"`) só aponta para o arquivo.
- **Leitura de pastas** (`services/drive_scan.py`): estrutura
  `Categoria / Item N - descrição / AAAA-NNNN título / arquivos`; "(CANCELADO)" no
  nome marca tentativa cancelada. Só lê nomes e tamanhos (não abre os arquivos,
  para o OneDrive não baixar cada PDF). Pastas fora do padrão (viagens,
  reformulações, diárias por pessoa...) vão para "não reconhecidas", nunca
  viram processo à força. Tipo do documento e estado do processo são
  **inferidos pelo nome dos arquivos** (AF → autorizado; nota fiscal; "atestada"
  → concluído; pedido de importação → autorizado) e podem ser corrigidos depois.
- **Planilha de valores** (`services/ledger.py`): lê as abas de lançamentos por
  categoria localizando as colunas pelo **título do cabeçalho** (os layouts
  diferem: algumas abas têm "Quantidade"). Linhas com nº de processo inválido
  são listadas **com o valor**, para o dinheiro não sumir em silêncio.
- **Sincronização** (`services/drive_sync.py`): plano sem gravar (`scan`) e
  aplicação (`sync`). Idempotente (chave = nº do processo). Regras: quem está na
  planilha e só tem cotação na pasta entra como **autorizado** (realizado);
  lançamentos que só existem na planilha (sem pasta) também são criados, sem
  arquivos; item inexistente no orçamento é reportado, não criado.
- **Endpoints** (`/projects/{id}/drive/...`): `GET status`, `POST scan`,
  `POST sync` (coordenador), `GET browse?path=`, `GET file?path=`. Caminhos
  passam por `join_rel`/`safe_join` (sem `..`, caminho absoluto, `C:`).
- **Caminhos longos no Windows** (>260 caracteres, comuns nas pastas reais):
  tratados com o prefixo `\\?\` (`core/drive.py::fs_path`).
- **Validado em dados reais** (num banco descartável, depois apagado): 420
  processos e 1.772 arquivos lidos em < 1 s; sincronização em ~1,2 s,
  idempotente; o "realizado" do programa bate com a soma dos lançamentos da
  planilha em todas as categorias com dados; download de um PDF real (~400 KB)
  pela API funcionou.

### Frontend

- Novas telas: **Drive** (ler pastas → conferir plano → sincronizar; navegar e
  baixar arquivos) e **Configurações** (pasta do drive, política de saldo,
  parcelas).
- **Resumo**: quadro resumo (grupos, total, parcelas com % utilizado, aviso de
  itens com saldo negativo).
- **Orçamento**: coluna "Qtd. disponível".
- **Processo**: documentos do drive (marcados "drive", seletor de tipo,
  "desvincular"), todos os tipos de documento listados, histórico do processo,
  aviso de origem "criado a partir da pasta do drive", justificativa para
  dispensar documento (coordenador).
- **Novo processo**: bloqueia ou só avisa conforme a política do projeto.
- `ProjectContext` ganhou `reloadProject`.

### Testes

51 → **96** testes do backend. Arquivos novos: `test_drive.py` (leitura de
pastas, planilha, sincronização, consulta, tentativas de sair da pasta),
`test_parity.py` (quantidade disponível, parcelas, resumo, política de saldo,
override, histórico, nº único, limite de upload), `test_migrations.py` (banco
antigo). `test_accrual.py` reescrito para a regra da planilha. Dois testes
antigos foram atualizados por descreverem a regra anterior e um usou valor
menor para não estourar o saldo (testa permissão, não saldo).

### Documentação

- `docs/CHANGELOG.md` (este arquivo), `docs/ESTADO_E_PLANOS.md`,
  `docs/AGENT_CONTRACT.md`, `CLAUDE.md`.

---

## Em andamento — `wip/drive-agent` (modo agente do drive)

Objetivo: o backend (Docker, servidor do laboratório) **não** precisa enxergar a
pasta do OneDrive; o **Horun Agent**, num PC com o OneDrive sincronizado,
consulta o servidor e lê os arquivos por ele (mesmo desenho do RE7S).

Já escrito (nesta branch):

- `docs/AGENT_CONTRACT.md` — contrato com o agente: operação `list_tree`,
  `read_file` em pedaços, códigos de erro, root somente leitura, caminhos longos
  no Windows, versão. **Achado crítico**: o agente atual monta a tarefa com
  `Task(**t)` (estrito); campo desconhecido derruba o laço dele, por isso o
  servidor só envia campos novos a quem declarar `X-Horun-Agent-Version >= 0.2`.
- `core/config.py` — `MODULE_DRIVE_MODE` (`local`|`agent`),
  `MODULE_DRIVE_AGENT_ROOT`, `MODULE_AGENT_TASK_TIMEOUT`, `MODULE_AGENT_CHUNK_MB`,
  `MODULE_AGENT_MAX_FILE_MB`.
- `db/models/agent.py` — `AgentEnrollCode`, `AgentDevice`, `AgentTask`.
- `services/agent_bridge.py` — enfileira a tarefa e espera o resultado; falha
  rápida se nenhum agente foi visto em 120 s; tarefa que estourou o prazo vira
  `expired` (no RE7S continua pendente e seria executada tarde); arquivos em
  pedaços com limite; recusa `list_tree` se o agente é antigo.
- `api/routes_agent.py` — `/agent/enroll-codes`, `/agent/devices`,
  `/agent/devices/{id}/revoke` (admin do Core); `/agent/enroll`,
  `/agent/tasks`, `/agent/tasks/{id}/result` (token do dispositivo).
- `core/drive.py` **reescrito** (`DriveError`, `DriveNotFound`, `fs_path`,
  `safe_join`, `join_rel`, `drive_root`) e `core/drive_backend.py` novo
  (`DriveBackend`, `LocalDrive`, `AgentDrive`, `get_drive_backend`,
  `serve_file`).

**Ainda não religado** (por isso a suíte não importa nesta branch): os módulos
abaixo ainda importam funções que saíram de `core/drive.py`
(`project_drive_dir`, `resolve_drive_folder`). Passos restantes na seção
"Modo agente — o que falta" de [`ESTADO_E_PLANOS.md`](ESTADO_E_PLANOS.md).
