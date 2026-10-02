# Contrato Financeiro ↔ Horun Agent (extensões ao `PROTOCOL.md`)

> **Status (2026-10-02): implementado no Agent-Horun 0.4.0** e no pacote único
> do servidor do agente, que esta branch já usa (`backend/app/agent_server/`,
> cópia gerada por `Agent-Horun/scripts/vendor_server.py` — não edite lá).
> `services/agent_bridge.py`, `api/routes_agent.py` e `db/models/agent.py`
> viraram fachadas finas; testes em `tests/test_agent_package.py`.
> O texto abaixo é o pedido original. **Diferenças em relação a ele** (vale o
> `PROTOCOL.md` do Agent-Horun):
>
> | Pedido aqui | Como ficou |
> |---|---|
> | `offset`/`length`/`recursive` soltos na tarefa | dentro de `args` (`{"offset", "length"}`, `{"recursive"}`) |
> | `X-Horun-Agent-Version: 0.2` | versões reais: leitura em pedaços ≥ 0.3.0, `list_tree` ≥ 0.4.0; sem cabeçalho = 0.2.0 |
> | `truncated: true` acima de 50.000 itens | erro `code: "too_large"` (peça uma subpasta) |
> | `"read_only": true` | aceito; equivale a `"mode": "read"` (também há `read-move`, `read-write`) |
> | `result_entries`, `result_error_code`... | colunas do pacote: `result_paths` (JSON das entradas), `result_code` |
> | gateway do Core liberar `/m/financeiro/agent/*` | **não**: porta estreita própria (ver "Rede" abaixo) |
>
> ## Rede — como o agente chega ao Financeiro
> Como no RE7S (`frontend/nginx.conf`, segundo `server { listen 8001; }`): uma
> porta própria que só repassa `/agent/enroll`, `/agent/tasks` e
> `/agent/tasks/{id}/result` ao backend — em `/api/agent/...`, porque aqui a
> API inteira vive sob `/api` — e responde 404 ao resto
> (`client_max_body_size 50m`). Proposta: **8002**, publicada no compose e com
> regra no Firewall do Windows do servidor. No `config.json` do agente:
> `"url": "http://192.168.31.80:8002"`. Conferência: `curl
> http://<servidor>:8002/agent/enroll-codes` tem que dar 404. O Core não muda.

O Horun Financeiro lê o drive do projeto (pasta do OneDrive) por dois caminhos,
escolhidos por `MODULE_DRIVE_MODE`:

- `local` (padrão): o backend lê a pasta direto do disco (`MODULE_DRIVE_ROOT`).
- `agent`: o backend NÃO enxerga a pasta; pede ao **Horun Agent**, instalado no PC
  onde o OneDrive está sincronizado, que leia por ele. O servidor nunca abre
  conexão com o PC — o agente é quem consulta (`GET /agent/tasks`), como no RE7S.

O `PROTOCOL.md` do agente (`enroll`, `tasks`, `tasks/{id}/result`) **não muda**.
Este documento só acrescenta o que o Financeiro precisa. Tudo é retrocompatível:
um agente antigo continua funcionando para as operações antigas.

O Financeiro usa uma única pasta liberada (root) chamada **`financeiro`**
(configurável no servidor por `MODULE_DRIVE_AGENT_ROOT`), apontando para a pasta
que CONTÉM a pasta de cada projeto (ex. `...\Programas\Maturação artificial`).
O Financeiro só LÊ — nunca pede `write_file`.

## 1. Nova operação: `list_tree`

Lista pastas **e** arquivos (com tamanho). Necessária porque `list_files` só
devolve arquivos: pastas sem arquivo (ex. um processo `(CANCELADO)` vazio) somem,
e o Financeiro precisa do tamanho de cada arquivo.

**Tarefa** (em `GET /agent/tasks`):
```json
{ "id": 7, "op": "list_tree", "root": "financeiro",
  "path": "Guilherme - 25465 Maturação Artificial",
  "recursive": true, "glob": null, "content_base64": null }
```
- `path`: pasta a listar, relativa ao root, posix. Vazio = o próprio root.
- `recursive`: `true` = toda a subárvore; `false` = só o primeiro nível.

**Resultado** (`POST /agent/tasks/{id}/result`):
```json
{ "ok": true,
  "entries": [
    { "path": "Guilherme - 25465 Maturação Artificial/Passagens", "is_dir": true,  "size": null },
    { "path": "Guilherme - 25465 Maturação Artificial/Passagens/a.pdf", "is_dir": false, "size": 12345 }
  ],
  "truncated": false }
```
- `path` de cada entrada é relativo ao **root** (não ao `path` pedido), posix,
  e não inclui a própria pasta pedida. Ordenado por `path`.
- Ignorar nada: o filtro de arquivos temporários é do servidor.
- Limite de segurança: no máximo 50.000 entradas; se passar, devolver as
  primeiras e `"truncated": true` (o servidor trata como erro).
- Pasta inexistente → `{"ok": false, "error": "...", "code": "not_found"}`.

## 2. `read_file` em pedaços e com tamanho

Hoje lê o arquivo inteiro e devolve em base64. O Financeiro passa a pedir
**pedaços** (PDFs escaneados podem ter dezenas de MB).

**Tarefa**: `read_file` ganha dois campos opcionais, `offset` (padrão 0) e
`length` (padrão `null` = até o fim, respeitando o limite do agente):
```json
{ "id": 8, "op": "read_file", "root": "financeiro",
  "path": "Proj/Passagens/a.pdf", "offset": 0, "length": 4194304 }
```
**Resultado**:
```json
{ "ok": true, "content_base64": "...", "size": 400936, "offset": 0 }
```
- `size` = tamanho TOTAL do arquivo; o servidor usa para saber se faltam pedaços.
- Agente antigo (sem `size`): o servidor entende que `content_base64` é o
  arquivo inteiro. Por isso o agente novo deve sempre mandar `size`.
- Limite próprio do agente (`max_read_bytes`, sugestão 8 MiB por pedaço): se
  `length` pedido (ou o arquivo inteiro, quando `length` é nulo) passar disso →
  `{"ok": false, "code": "too_large", "error": "..."}`.

## 3. Códigos de erro

`{"ok": false, "error": "<mensagem>", "code": "<código>"}` — `code` é opcional e
um destes: `not_found`, `outside_root`, `unknown_root`, `read_only`, `too_large`.
`error` continua sendo o texto para humanos (o servidor também reconhece
"não encontrado" no texto, como o RE7S faz hoje).

## 4. Pasta somente leitura

No `config.json` do agente, cada root pode ser marcado somente leitura:
```json
{ "roots": { "financeiro": { "path": "C:\\...\\Maturação artificial", "read_only": true } } }
```
(O formato antigo — `"roots": {"data": "C:\\..."}` — continua valendo, como
leitura e escrita.) `write_file` em root somente leitura → `code: "read_only"`.

## 5. Caminhos longos no Windows (obrigatório)

Os caminhos das pastas do projeto passam de 260 caracteres. No Windows, `pathlib`
sem o prefixo `\\?\` falha em `is_file()`, `glob`, `read_bytes` etc. O agente
precisa operar com caminhos prefixados (`\\?\C:\...`) em todas as operações, e
devolver sempre caminhos **sem** o prefixo e em posix.

## 6. Versão (OBRIGATÓRIO no agente novo)

O agente novo envia `X-Horun-Agent-Version: 0.2` em **todo** `GET /agent/tasks`.

Isto não é cosmético: o agente atual monta a tarefa com `Task(**t)` (dataclass
estrita), então um campo desconhecido (`offset`, `length`, `recursive`) lança
`TypeError` — que o laço não trata — e **derruba o agente**. Por isso o
servidor só envia os campos novos a quem declara versão ≥ 0.2; a quem não
declara, envia exatamente os seis campos de sempre
(`id, op, root, path, content_base64, glob`) e nunca oferece `list_tree`.

Requisitos para o agente 0.2:
- enviar o cabeçalho acima em toda consulta;
- o `Task` tolerar campos extras (ou ter `offset`, `length`, `recursive` com
  padrão `None`) — recomendável mesmo sem a versão, por robustez;
- `id` pode vir como número (o servidor do Financeiro usa inteiros).

Servidor sem agente 0.2 online: `list_tree` falha com mensagem "agente
desatualizado" (não fica pendente para sempre). `read_file` continua
funcionando com agente antigo, só que sem pedaços (arquivo inteiro).

## Prompt para a sessão do agente

Feito — Agent-Horun 0.4.0 (ver o status no topo).
