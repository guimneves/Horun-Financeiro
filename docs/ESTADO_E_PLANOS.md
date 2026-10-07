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
  Há também `antiga.xlsx`, `antiga 2.xlsx`, `Calculo Pessoal.xlsx` (a
  sincronização as ignora e usa a de "Acompanhamento") e uma folha de pessoal
  dentro de `Equipe Executora`.
- A planilha tem inconsistências próprias (ex.: verificação com `#REF!`, soma
  de grupo que omite uma linha, uma fórmula de saldo que desconta rendimento de
  forma diferente das outras). Servem de argumento para o programa, mas a
  reconciliação deve saber que os números dela podem estar errados.
- Linhas de lançamento **sem nº de processo** (coluna vazia, "?", "x", uma data,
  um ID de seguro): DOA, ressarcimentos, passagens pela agência, diárias. Entram
  como "lançamento sem nº" no item da coluna "Nº do Item" (`ledger_ref`).
- **Não há pasta de Outras Despesas** no drive; em `Passagens`, `Diárias` e
  `Ajuda de custo` nenhuma subpasta segue o padrão `Item N/processo` — esses
  gastos vêm só da planilha.
- **Subitem** "1.1" na coluna "Nº do Item" (Serviços): é uma linha própria do
  SIGITEC, diferente do item 1 (pendência, seção 8).
- Itens de Material de Consumo/Serviços com quantidade 1 são **verbas** (várias
  compras por item).
- As datas de modificação dos arquivos do drive são todas iguais (a da cópia
  para o OneDrive) — não servem como data da compra. O nº de processo COPPETEC
  é sequencial no ano (~13.800/ano) e dá a data aproximada (`services/pace.py`).
- **Conferência (02/10/2026)**: depois da sincronização, o realizado dos 274
  itens de despesa é igual ao da coluna "Valor Realizado" da aba Saldo por Item,
  ao centavo. Equipe Executora difere porque o módulo conta até hoje.

## 5. Estado atual por branch

- **`master`** (única desde 06/10/2026): **268 testes** do backend passam;
  frontend compila e passa no lint. Inclui o modo agente do drive (a
  `wip/drive-agent` foi incorporada) e a configuração de produção:
  `docker-compose.yml` (Postgres, backup, porta 8002 do agente) e o passo a
  passo em `docs/DEPLOY.md`. Mesmo código nos dois modos: servidor com
  `MODULE_DRIVE_MODE=agent`, testes locais com `local`.
- **Sincronização com o drive nos dois sentidos** (06/10/2026, decisão 13):
  anexos copiados para a pasta do processo (`MODULE_DRIVE_WRITE`, padrão
  desligado), pasta "SEM NUMERO" renomeada quando o nº chega, nº lido da
  autorização de fornecimento, sincronização automática a cada
  `MODULE_DRIVE_AUTO_SYNC_MINUTES` (padrão 30). Ainda não testada com o
  agente real em "read-write".
- **Papéis pelo cargo no Horun** (06/10/2026, decisão 14): atrás do Core não há
  senha de coordenador nem cadastro de membros para entrar; o cabeçalho mostra
  o papel e "← Voltar ao Horun". A senha mestra e o "Ver como" seguem só no
  modo DEV (o `.bat`).
- **Apresentação local**: `Programas/Horun/Apresentar_Financeiro.bat` (fora do
  repositório) roda a `master` em modo DEV com o drive local e a base em
  `C:\HorunDemo\Financeiro`. Reabrir o .bat a cada mudança; a planilha precisa
  estar fechada no Excel para ser lida.
- Nada disso foi testado em produção; não há deploy.

## 6. Decisões já tomadas (não reabrir sem motivo)

1. **Meses da equipe**: regra da planilha (calendário, pago no mês seguinte).
2. **"Realizado"**: regra da planilha (nº de processo lançado = realizado).
3. **Saldo**: aceitou bloquear estouro, depois pediu flexibilidade → política por
   projeto (bloquear | avisar), padrão bloquear.
4. **Ordem do trabalho**: paridade → corrigir a base → leitura de pastas.
5. **Importação**: o programa lê pastas e a planilha por si só (não um CLI
   externo); começa lendo (plano sem gravar), só grava após confirmação.
6. ~~Não importar dados reais ainda~~ — o orçamento já é importado da
   planilha; os dados reais ficam só na base local da apresentação (fora do
   repositório).
7. **Alembic não adotado**: manter `_ensure_column` como o Horun Core; decidir
   junto com o Core se migra.
8. **Bifurcação do trabalho do agente**: uma sessão trabalha no Financeiro, outra
   no repositório **Horun Agent**. O contrato entre as duas está em
   [`AGENT_CONTRACT.md`](AGENT_CONTRACT.md).
9. **Item vem da planilha**, não da pasta (02/10/2026): o "Nº do Item" da
   planilha corresponde 1 a 1 ao SIGITEC — preservar essa numeração. A pasta só
   diz quais processos existem; processo já importado no item da pasta passa
   para o da planilha ao sincronizar (se ninguém mudou à mão).
10. **Lançamentos sem nº de processo** contam como realizado (como na planilha).
11. **Data da compra no gráfico de ritmo**: `realized_on` (gravada ao autorizar)
    ou, nos importados, estimada pelo nº de processo — o painel diz quanto é
    estimado.
12. Ordem da apresentação aos supervisores: rodar localmente antes de implantar
    no Horun.
13. **Drive e módulo sempre sincronizados, nos dois sentidos** (06/10/2026 —
    REVERTE a regra "o módulo só lê o drive" e a escrita "descartada" da
    seção 10): (a) todo documento anexado num processo também é gravado na
    pasta dele no drive; (b) o que aparece nas pastas entra no módulo sozinho,
    pela sincronização automática periódica. Regras: lê sempre; escreve só
    arquivos NOVOS e só com `MODULE_DRIVE_WRITE=true` (padrão desligado — a
    apresentação local aponta para o OneDrive real); nunca sobrescreve
    ("nome (2).pdf"), nunca apaga; só move os arquivos da própria pasta
    "SEM NUMERO <dd-mm-aaaa> <título>" quando o processo ganha o nº. No modo
    agente, o root precisa de `"mode": "read-write"`. Processo sem nº:
    pasta "SEM NUMERO" com a data de criação (escolha do mantenedor). O nº é
    lido da autorização de fornecimento ("AUTORIZAÇÃO DE COMPRA AAAA/N") e
    nunca sobrescreve um nº já cadastrado. Arquivo desvinculado no módulo não
    volta a ser vinculado pela sincronização (`DriveUnlinkedPath`).
14. **Papéis vêm do cargo no Horun no modo módulo; senha mestra só no
    desenvolvimento** (06/10/2026 — pedido do mantenedor: "a senha de
    coordenador no módulo só atrapalha"). Fora do `HORUN_DEV_MODE`, o
    `X-Horun-Level` do Core decide: 1 (administrador máximo) e 2
    (coordenador/a) são coordenador em TODOS os projetos; 3–5 (e quem chega
    sem nível) são colaborador em todos — todos veem todos os projetos,
    colaborador sem R$. Sem `X-Horun-Level` (Core antigo), `X-Horun-Role`
    "admin" vale nível 2. A senha mestra é ignorada (rotas de senha
    respondem 409). `ProjectMembership` passa a ser só "participantes do
    projeto": os marcados como coordenador recebem os avisos; sem nenhum, o
    aviso vai aos níveis 1–2 do Core. No DEV_MODE (`Apresentar_Financeiro.bat`)
    tudo segue como antes (membros + senha mestra + "Ver como"). Sem
    variável nova: o critério é só `HORUN_DEV_MODE` (`module_mode()` em
    `core/permissions.py`) — só 12 testes dependiam do esquema antigo e
    passaram a usar o fixture `dev_mode`. A mesma lógica deve ir para
    Reagentes e Amostras.

## 7. Modo agente — divisão de trabalho e o que falta

### Contexto
O OneDrive está sincronizado num PC; o backend vai rodar em Docker (provavelmente
no servidor do laboratório). O backend só lê a pasta como caminho local; no modo
agente, o **Horun Agent** (já existe em `Programas/Horun Agent`, com a ponte do
lado servidor no RE7S) lê por ele. O agente consulta o servidor (nunca o
contrário), então o PC não abre porta.

### Lado do agente — FEITO (Agent-Horun 0.4.0, 2026-10-02)
O servidor do agente é o pacote único (`backend/app/agent_server/`, o mesmo do
RE7S — para atualizar: `python scripts/vendor_server.py "<Financeiro>/backend"`
no Agent-Horun). Diferenças em relação ao pedido original estão no topo do
`AGENT_CONTRACT.md` (campos em `args`, versões 0.3/0.4, porta estreita em vez
de liberar o gateway do Core).

### Lado do Financeiro — FEITO na `wip/drive-agent` (2026-10-02)
- Todo acesso ao drive passa por `core/drive_backend.py` (`get_drive_backend()`:
  `LocalDrive` | `AgentDrive`), com caminhos relativos à raiz do drive
  (`join_rel(project_folder(...), ...)`): scan/sync, planilha, navegação,
  download de arquivo e de documento "drive" (`core/files.document_response`).
- `services/drive_scan.scan_entries(entries)` monta a leitura a partir da lista
  plana do `list_tree` (mesma ordem e regras de antes; pastas vazias contam);
  `scan_project_folder(path)` virou atalho para o disco local.
- `services/ledger.read_ledger` aceita o conteúdo em bytes.
- `core/drive.py`: as proteções da master (`:` e NUL em qualquer segmento,
  `commonpath`, pasta do projeto ≠ raiz) valem para os dois modos.
- Pasta do projeto: no modo agente só a sintaxe é validada ao salvar (não
  depende do PC estar ligado); no local, também a existência.
- `GET .../drive/status` ganhou `mode`; no modo agente diz se o agente está
  conectado e se é novo o bastante, **sem** mandar tarefa ao PC. A tela do drive
  mostra o aviso e "Verificar de novo".
- Rotas `/api/agent/*` (pacote) dentro da lista `/api` do `main.py`.

### O que falta (depende do ambiente real)
1. **Decidir onde o backend roda e em qual PC o OneDrive fica** (seção 8).
2. **Porta estreita do agente** (proposta 8002): um segundo `server {}` no
   nginx do frontend, como o do RE7S, repassando só `/agent/enroll`,
   `/agent/tasks` e `/agent/tasks/{id}/result` para o backend em
   **`/api/agent/...`** (aqui a API vive sob `/api`); publicar a porta no
   compose de produção e liberar no firewall. Conferência:
   `curl http://<servidor>:8002/agent/enroll-codes` → 404.
3. **Compose de produção**: `MODULE_DRIVE_MODE=agent`, `MODULE_DRIVE_AGENT_ROOT`
   (padrão `financeiro`), timeout/limites (`core/config.py`).
4. ~~Tela de admin do agente~~ — feita: painel "Horun Agent (drive)" em
   Organização (`components/AgentPanel.tsx`, o mesmo do RE7S): gerar código de
   instalação, ver instalações (conectado/sem sinal, versão) e revogar. Só o
   admin do Core enxerga (para os outros a listagem dá 403 e o painel some).
5. No PC do OneDrive: Agent-Horun 0.4.0, `config.json` com o root `financeiro`
   apontando para a pasta que contém as pastas dos projetos — em
   `"mode": "read-write"` se o servidor tiver `MODULE_DRIVE_WRITE=true`
   (decisão 13), senão `"mode": "read"`.

### Consequências aceitas do modo agente
Latência de um intervalo de consulta por ação; sem o PC ligado não se lista nem
baixa arquivo (processos/documentos já cadastrados continuam consultáveis); um
mesmo agente pode atender vários módulos no mesmo PC (`servers` no
`config.json`, desde 0.3.0).

## 8. Pendências e decisões em aberto

- **Subitens** ("1.1", "1.2"...) no orçamento, com previsto e saldo próprios —
  hoje o gasto do 1.1 cai no item 1 e o previsto dele não é importado (item 1 de
  Serviços fica negativo). Proposto; aguardando o usuário.
- **Onde o backend vai rodar** e **em qual máquina o OneDrive está
  sincronizado** (serão máquinas separadas — ainda sem decisão). Define a porta
  estreita 8002 e o compose de produção.
- **Estados dos processos importados** são inferência pelos arquivos; a maioria
  fica "nota fiscal emitida" (só 2 "concluído"). Aceitar assim ou outra regra?
- **12 processos com pasta e sem valor na planilha** entram com valor zero
  (alerta "sem valor" no Resumo).
- Equipe Executora acima do saldo: **não bloqueia** — confirmar.
- `MAX_QUOTES_PER_PROCESS = 3` é um **máximo**; se a regra da fundação é um
  **mínimo** de 3 cotações, o modelo está invertido — confirmar.
- Alembic × `_ensure_column` (decidir com o Core).
- ~~Build Docker do frontend sem o design-system~~ — resolvido em 2026-10-02:
  cópia versionada em `frontend/vendor/horun-design-system/` (gerada por
  `Horun-Core/scripts/vendor_design_system.py`; `--check` diz se ficou
  desatualizada). Não edite a cópia: mude no Core e rode o script de novo.
- ~~`wip/drive-agent` precisa ser atualizada com o `master`~~ — feito em
  2026-10-02. As rotas do agente ficam sob `/api` (laço em `main.py`); a porta
  estreita repassa `/agent/...` para `/api/agent/...`, então o `url` do agente
  continua sendo só `http://<servidor>:8002`.
- ~~Cadastrar o orçamento~~ / ~~importar a Equipe Executora~~ / ~~linhas
  inválidas da planilha~~ — feitos em 02/10 (importação pela tela e
  lançamentos sem nº).

## 9. Plano (ordem sugerida)

1. Subitens no orçamento (se aprovado).
2. Exportar o Resumo (PDF/Excel) para os supervisores.
3. **Fluxos por categoria** (hoje há um fluxo único, o de compra): Afastamento do
   País (carta convite, cartão de embarque, hotel, passagem, relatório, seguro),
   Diárias/Ajuda de custo, Serviço, Prestação de contas — cada um com seus
   documentos e estados.
4. **Documentos de projeto** (Documentos COPPETEC, SEI, reformulações, Comodato):
   hoje documento só se liga a processo de compra ou atribuição de pessoal.
5. Câmbio nos itens importados; coluna "confere" da planilha; comparar revisões.
6. Terminar o modo agente no ambiente real (seção 7) e
   Docker/compose de produção com o Core.
7. Endurecer: concorrência (versão otimista), paginação, fuso de `date.today()`,
   revisão do uso de `MODULE_SECRET_KEY` (hoje sem uso).

## 10. Ideias discutidas (backlog completo)

Implementadas: ver CHANGELOG. Discutidas e **não** feitas:

- **Fluxos por categoria** e **documentos de projeto** (itens 3–4 acima).
- **Exportar o Resumo** em PDF/Excel; **coluna "confere"** da planilha;
  **comparar revisões** do orçamento.
- **Moeda estrangeira/câmbio** para categorias importadas (hoje só uma nota de
  texto): campos de moeda, valor original, taxa e data.
- **Ligar tentativas**: pasta "(CANCELADO)" ao irmão com mesmo título
  (`previous_attempt_id`) — heurística de título; não implementada por risco.
- **Alternativas de armazenamento para servidor Linux** (descartadas em favor do
  agente, mas válidas): pasta montada por SMB; `rclone` espelhando o OneDrive;
  integração direta com a API do OneDrive (Microsoft Graph).
- **Aviso do OneDrive "Files On-Demand"**: ler arquivo só-nuvem o baixa; em Docker
  no Windows pode falhar — marcar a pasta "manter sempre neste dispositivo".
- **Camada de armazenamento abstrata** com pasta legível por humanos (feita
  via `DriveBackend`). A escrita de volta no drive, antes **descartada**, foi
  adotada em 06/10/2026 (decisão 13 da seção 6).
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
3. Instalar e rodar a suíte (seção 3). Na `master` deve dar **268 passed**.
4. As memórias da sessão original ficam fora do repositório (no perfil do
   Claude Code da conta antiga); o essencial delas está na seção 1 e 6 acima.
5. Contexto externo: `Programas/Horun Core` (design-system e plataforma),
   `Programas/Horun Agent` (agente), `Projeto Horun/Rock Eval Horun Dev` (RE7S:
   referência do padrão de agente e de módulo).
