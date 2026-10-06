# Changelog — Horun · Financeiro

Registro do que mudou desde o último commit do repositório
(`98ea7d4 — Correcoes da revisao de codigo: 10 achados confirmados`), na
sessão de trabalho iniciada em 29/09/2026. Para o estado atual, decisões e
plano, ver [`ESTADO_E_PLANOS.md`](ESTADO_E_PLANOS.md).

Desde 06/10/2026 há uma branch só, a `master` (o modo agente, antes na
`wip/drive-agent`, foi incorporado): 235 testes do backend passam; frontend
compila (`tsc -b`) e passa no lint.

---

## 06/10/2026 — Pronto para o servidor (modo agente na master)

- A `wip/drive-agent` entrou na `master` (avanço direto, sem conflito): o modo
  agente do drive vale no servidor e o modo local continua no `.bat` de testes.
- `docker-compose.yml` passa a ser o de **produção**: Postgres, `db-backup`,
  `financeiro-backend`/`financeiro-frontend` na `horun-network`, sem porta da
  API no host; só a **8002**, porta estreita do Horun Agent (`frontend/nginx.conf`,
  repassa `/agent/...` para `/api/agent/...`). O antigo virou
  `docker-compose.dev.yml` (standalone de desenvolvimento).
- Imagem do backend com o extra `import` (openpyxl): sem ele, importar a
  planilha falharia no servidor.
- `.env.example` de produção; `docs/DEPLOY.md` com o passo a passo (servidor,
  cadastro no Core, instalação do agente no PC do OneDrive, carga do projeto).

## 05/10/2026 — Aba Manual, interface no celular e avisos pelo Core

- **Aba Manual** (última da barra lateral, para todos): para que serve, quem
  pode fazer o quê, uma seção por tarefa com os botões em negrito, dúvidas
  frequentes e quem procurar. Índice com âncoras, busca por texto e
  **Imprimir / salvar PDF** (`window.print()`, sem barra lateral nem
  cabeçalho). Conteúdo em `frontend/src/manual/content.tsx` — mudou uma tela,
  atualize o manual no mesmo commit.
- **Celular (375 px)**: barra lateral vira gaveta (☰; fecha ao escolher, ao
  tocar fora e com Esc); Orçamento (categorias e itens), Compras e Equipe em
  cartões; gráfico por categoria com rótulos curtos; tabelas largas (Quadro
  resumo, Drive, Revisões, Membros) rolam para o lado; modais na largura toda
  com rolagem interna; campos com fonte de 16 px e botões com 40 px de altura;
  no processo, as **Ações** vêm antes dos documentos. Computador igual a antes.
- **Avisos pelo Horun Core** (sininho + e-mail; `core/notify.py`,
  `services/notifications.py`): compra enviada para autorização →
  coordenadores do projeto; autorizada/rejeitada → quem criou o processo; nota
  fiscal acima do saldo → coordenadores. Sem valores em R$ nos textos; quem fez
  a ação não é avisado. Liga com `HORUN_CORE_URL` + `HORUN_NOTIFY_TOKEN` (chave
  gerada em Core → Admin → Módulos → Notificações); sem elas, nada muda.
  Detalhes no README. 12 testes novos (214 no total).

## 02/10/2026 — Item da planilha (SIGITEC) e Orçamento por categoria

- **Vale o "Nº do Item" da planilha**, não o "Item N" da pasta (decisão do
  usuário: a numeração da planilha corresponde 1 a 1 à do SIGITEC). Processo
  novo entra no item da planilha, com aviso; processo já importado que ficou
  no item da pasta passa para o da planilha na próxima sincronização
  ("Itens a corrigir"; só se ninguém trocou o item à mão). Conferido com a
  planilha real: os 274 itens de despesa batem ao centavo.
- **Orçamento por categoria**: a aba mostra primeiro as categorias (totais,
  itens com saldo negativo, % usado); cada uma se expande nos itens.
- Pendente: subitem ("1.1") é uma linha própria do orçamento, diferente do
  item 1 — hoje o gasto dele cai no item 1 e o previsto dele não é importado.

## 02/10/2026 — Sincronização bate com a planilha, categoria a categoria

Conferido com a planilha real: o realizado de todas as 12 categorias de
despesa agora é igual ao da coluna "Valor Realizado" da aba Saldo por Item
(só a Equipe Executora difere, por contar até hoje).

- **Lançamentos sem nº de processo** (DOA, ressarcimentos, passagens pela
  agência, diárias, linhas com "?" ou data na coluna do processo) entram como
  realizados no item da coluna "Nº do Item" (`origin = planilha_sem_numero`,
  sem arquivos). Identidade da linha em `ledger_ref` (pelo conteúdo — não
  duplica ao sincronizar de novo); data na coluna do processo vira
  `realized_on`. Antes eram descartados sem aviso.
- **Subitem "1.1"** na coluna "Nº do Item" conta no item 1, com aviso.
- **Preencher valor**: processo que entrou com R$ 0 (sincronizado sem a
  planilha) recebe o valor da planilha na próxima sincronização.
- **Planilha achada sozinha**: com o campo vazio, a sincronização usa a
  planilha de acompanhamento da pasta "0_Saldo por item" (ignora "antiga…").
  Visto na prática: o campo ficou vazio e 420 processos entraram com R$ 0.
- **"Quantidade disponível" de verba**: item de quantidade 1 em Material de
  Consumo, Serviços, Passagens, Diárias e Outras Despesas é uma verba gasta em
  várias compras — mostra "verba" em vez de 1 − 63 = −62.

## 02/10/2026 — Ritmo de execução no Resumo

- Gráfico "Ritmo de execução" (`services/pace.py`): realizado acumulado mês a
  mês (Equipe Executora e compras, em % do orçamento + rendimentos) × ritmo
  linear do prazo × parcelas previstas, com a marca de hoje.
- Equipe Executora entra mês a mês, exata (mesma conta de `accrual.py`).
- Compras entram na data do realizado: novo campo `realized_on` no processo
  (gravado ao autorizar pelo módulo, editável via PATCH; `_ensure_column`).
  As importadas do drive não têm data — as datas dos arquivos são as da cópia
  para o OneDrive (todas iguais) — e são **estimadas pelo nº de processo
  COPPETEC** (ano do número; dentro do ano, ~13.800 números/ano, quase
  linear — medido em processos cujos arquivos têm a data no nome). O painel
  diz quanto do realizado está com data estimada.
- O Resumo recarrega ao voltar para a aba do navegador.

## 02/10/2026 — Novo Resumo, com gráficos

- **Aba Resumo** refeita (`GET /api/projects/{id}/dashboard`,
  `services/dashboard.py`): indicadores (orçamento + rendimentos, realizado,
  comprometido, % do prazo decorrido × % executado); "Uso do orçamento por
  categoria" (barras empilhadas realizado / comprometido / saldo / estouro,
  Recharts 2.15.4); o Quadro Resumo da planilha em tabela (Capital e
  Correntes com subtotais, link para os itens da categoria); parcelas
  recebidas × usadas; "Precisa de atenção" (saldo negativo, item acima de
  90%, compra parada há 30+ dias antes da autorização, processo sem valor).
  Colaborador vê o mesmo painel em percentuais, sem R$.
- Configurações: vigência do projeto (início e fim), para o % do prazo.
- Orçamento aceita `?category=` (só uma categoria) — usado pelos links do Resumo.
- Saem `OverviewSection` e `CategorySummaryCard` (substituídos).
- **Achados ao conferir com a planilha real** (ainda não corrigidos): a
  leitura das abas de lançamento descarta, sem avisar, linhas sem nº de
  processo COPPETEC (quase todas de Passagens, Diárias e Outras Despesas —
  DOA, ressarcimentos, agência de viagem); e a sincronização põe cada
  processo no item da PASTA, enquanto a planilha usa a coluna "Nº do Item"
  — os totais por categoria batem, os itens não (daí saldos negativos
  falsos em itens).

## 02/10/2026 — Importar a Equipe Executora da planilha

- **Vagas** (Revisões → Importar da planilha): a 1ª tabela de Equipe
  Executora da aba "Saldo por Item" vira itens da categoria — uma vaga por
  linha, valor total mensal (valor + encargos) × "Período (em meses)";
  remuneração, modalidade e carga horária na observação do item. Uma 2ª
  tabela de Equipe Executora (na planilha real, com `#REF!`) é ignorada com
  aviso. Nº que junta vagas ("11, 22, 23, 24") vira a vaga do 1º número e as
  linhas avulsas desses números saem.
- **Pessoas** (Pessoal → Importar da planilha): aba "Equipe Executora" —
  pessoa, vaga, ativo/encerrado, início e fim de REFERÊNCIA, valor mensal.
  Prévia com o realizado da planilha ao lado do calculado pelo módulo;
  idempotente (mesma pessoa + vaga + início não repete). Conferido com a
  planilha real: na data da planilha, o realizado do módulo é igual ao dela,
  pessoa a pessoa. `services/personnel_import.py`, `tests/test_personnel_import.py`.
- Planilha aberta no Excel (o Windows trava o arquivo): "Ler pastas" e os
  envios de planilha dizem para fechar e tentar de novo, em vez de erro 500
  ou "Failed to fetch".

## 02/10/2026 — Ler arquivos sem baixar

- **Leitor na página**: clicar num PDF, imagem ou .txt (navegação do Drive e
  documentos do processo de compra) abre o arquivo numa janela sobre a
  página, no leitor do próprio navegador — com "Abrir em nova aba" e
  "Baixar". As rotas de arquivo aceitam `?inline=true`; só PDF, imagem
  (png/jpg/gif/webp) e texto são exibidos (`PREVIEWABLE_TYPES` em
  `core/files.py`), o resto continua download — um HTML ou SVG exibido
  dentro do Horun rodaria script com a sessão de quem abriu. Sempre com
  `X-Content-Type-Options: nosniff`. `tests/test_file_preview.py`.
- Modo dev: `VITE_API_URL` (frontend) e CORS para qualquer porta local —
  permite uma segunda cópia para teste ao lado da que está aberta.

## 02/10/2026 — Importar o orçamento da planilha; criar projeto pela tela

- **Importar da planilha** (Revisões → "Importar da planilha"): lê a aba
  "Saldo por Item" da planilha de acompanhamento e cria uma revisão NOVA em
  rascunho com todos os itens (categoria, nº, descrição, justificativa,
  V. unitário, quantidade, rendimentos) — antes, ~140 itens à mão. Prévia
  por categoria antes de gravar (`POST .../budget-import/preview`), nada
  vale até ativar. Colunas achadas pelo título de cada seção (o cabeçalho
  muda entre elas; sem V. unitário/Quant., entra quantidade 1). Equipe
  Executora fica de fora (tela de Pessoal); subitem com número decimal
  ("1.1") vira aviso com o valor. Conferido com a planilha real: os totais
  batem com o Quadro Resumo e, depois, "Ler pastas" achou item para todos
  os 420 processos. `services/budget_import.py`, `tests/test_budget_import.py`
  (planilha sintética).
- **Novo projeto pela tela** (lista de projetos, só admin do Core): a rota
  existia, mas não havia botão. `GET /api/auth/me` diz à tela quem é admin.
- `api.postForm` no frontend; o `Content-Type: application/json` só vai em
  corpo JSON (antes ia em qualquer corpo).

## 01/10/2026 — Trabalho de 27–28/09 integrado + nota fiscal acima do saldo

- **Integrado** o que tinha ficado numa outra cópia local (branch
  `backup/coordenador-0928`): senha mestra de coordenador, redação de valores
  em R$ para colaborador, barra lateral com os projetos, página Organização,
  diretório próprio de usuários, "Ver como" (só dev), nº de processo COPPETEC
  por item, página própria do item de orçamento, verificação de
  disponibilidade (sim/não, sem mostrar o saldo).
- **Coerência entre as duas versões**: a mensagem de saldo insuficiente não
  cita valores para colaborador; parcelas e visão geral passam a ser só do
  coordenador; o histórico de eventos chega ao colaborador sem o detalhe.
- **Senha mestra endurecida** (o repositório é público): sem chave de
  assinatura padrão — fora do DEV_MODE o módulo não sobe sem
  `MODULE_SECRET_KEY` (32+ caracteres); sem senha inicial padrão
  (`MODULE_COORDENADOR_PASSWORD`); 5 erros bloqueiam a pessoa por 15 min.
- **Nota fiscal acima do saldo**: registrar a nota com valor final que passa
  do saldo do item devolve um aviso (HTTP 428) em vez de gravar; a tela mostra
  o aviso e oferece "Corrigir valor" ou "Registrar mesmo assim". Confirmada, o
  processo guarda quem confirmou e quando (`over_balance_confirmed_by/_at`) e
  aparece com o sinal "Acima do saldo" na lista de compras, na página do item
  e no detalhe. Vale para qualquer política de saldo (a nota é um fato).
- 163 testes do backend.

---

## 01/10/2026 — Correções da revisão de código (em `master`)

Revisão dos repositórios do Horun; os achados mais urgentes deste módulo:

- **Encaixe no Core**: toda a API passou para `/api/...` (`main.py`); o
  frontend usa um `API_BASE` único com `/api` (`api/client.ts`). Antes, plugado
  no Core, as chamadas caíam no frontend e voltavam `index.html`. `/health`
  continua na raiz.
- **Drive**: `safe_join` recusa `:` em qualquer segmento (no Windows,
  `pasta/D:/x` trocava de unidade e saía da pasta do projeto) e confere o
  resultado por `commonpath`; a pasta do projeto não pode ser a raiz do drive
  (`.`), que daria acesso aos documentos de todos os projetos.
- **Valores**: `app/core/money.py` — dinheiro `>= 0`, quantidade de compra
  `> 0`, máximo 2 casas (igual a `Numeric(14,2)`); valor calculado arredondado
  para centavos. Quantidade negativa liberava saldo bloqueado. `null` explícito
  em PATCH de campo obrigatório dava 500, agora 422. Erros 422 viram uma frase
  em português no `detail`.
- **Upload de pessoal**: limite de tamanho, sha256, evento de auditoria e
  bloqueio em atribuição encerrada (como o de compras).
- **Compose de desenvolvimento**: portas em `127.0.0.1` (o modo dev é "admin
  sem login"); aviso no log quando `HORUN_DEV_MODE` está ligado; healthcheck do
  frontend em `127.0.0.1`.
- 38 testes novos (134 no total).

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
