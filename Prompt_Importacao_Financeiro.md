# Prompt — Importar dados reais de um projeto pro Horun · Financeiro

> Cole este documento inteiro numa conversa do Claude Code que tenha acesso (1) à planilha de acompanhamento de saldo do projeto a importar, (2) às pastas de documentos de compra desse projeto, e (3) ao backend do Horun · Financeiro rodando (local, `HORUN_DEV_MODE=true`, ou já plugado no Horun do laboratório). Ele descreve o procedimento completo — cada projeto novo importado é independente dos demais, e a planilha/pastas de origem podem ter diferenças de estrutura em relação ao exemplo original ("Maturação Artificial", processo COPPETEC 25.465) usado para desenhar este módulo. Onde houver diferença, este documento diz explicitamente quando **parar e perguntar** em vez de adivinhar — mesma regra que rege todo o resto do Horun (`Prompt_Horun_Modulo.md`, seção 2).

## 1. Por que isto é um prompt, não um script fixo

Cada projeto financiado guarda seu histórico numa planilha derivada do mesmo modelo original, mas com anos de edição manual por cima — categorias em ordem diferente, uma coluna a mais, uma aba renomeada, uma pasta de item com nome digitado diferente do da planilha. Um script único e rígido vai quebrar ou, pior, **importar silenciosamente um valor errado**. Por isso a importação é conduzida por um agente com acesso a arquivos (você, Claude Code), seguindo este roteiro, escrevendo um script pequeno e descartável específico pra essa planilha quando a mecânica for direta, e **parando pra perguntar** sempre que a heurística não fechar com segurança — isto é dinheiro real de um projeto Petrobras, não um teste.

## 2. Antes de tocar em qualquer dado — elicitação

Antes do primeiro `POST`, confirme com o usuário:

1. **Caminho da planilha** e **caminho da pasta raiz** de documentos deste projeto.
2. **Metadados do projeto**: código do processo COPPETEC (`code`), nome (`name`), agência financiadora (default `Petrobras`), fundação (default `COPPETEC/UFRJ`).
3. **URL base da API** de destino (ex. `http://localhost:8000` em dev standalone) e se o servidor já está rodando (`HORUN_DEV_MODE=true` pra não precisar de cabeçalhos de identidade).
4. Se é uma **importação nova** (projeto ainda não existe no Horun) ou uma **reconciliação** de um projeto já parcialmente cadastrado — os passos de idempotência (seção 7) mudam o comportamento.

Nunca prossiga pra escrita de dados sem essa confirmação — mesmo que pareça óbvio pelo nome dos arquivos.

## 3. Passo 1 — mapear a estrutura da planilha

Abra a planilha (mesma técnica usada na análise original: `openpyxl`, `data_only=False` pra ver fórmulas, depois relançar com `data_only=True` se precisar dos valores calculados). Identifique:

- A aba de orçamento planejado (era `Saldo por Item` no exemplo original) — blocos contíguos de linhas, um por categoria, com colunas `Nº / Descrição / Justificativa / V. unitário / Quant. Prevista / Valor / Rendimentos / Quant. Disponível / Valor Realizado / Saldo`.
- As abas de execução por categoria (uma por categoria: `Equip. Nacional`, `Material de Consumo`, `Serv. Terceiros` etc.) — cada linha é uma compra já realizada, com `Nº do Item` (referência de volta ao item do orçamento), `Favorecido`, `Descrição`, `Valor`, `Nº de Processo COPPETEC`.
- A aba resumo (`Quadro Resumo`) — normalmente só serve de checagem cruzada, não precisa ser importada diretamente.
- A aba de pessoal (`Equipe Executora`) — colunas `Item`, `Membro`, `Situação` (Ativo/Encerrado), `Início`, `Fim`, `Valor` (mensal).
- Pastas de reformulação (ex. `1_Reformulação do projeto Nº1/2/3`) — cada uma vira uma `BudgetRevision` adicional, na ordem cronológica.

**Categorias fixas do módulo** (`GET /categories`, ou veja `backend/app/db/models/budget.py`): `equip_nacional`, `equip_importado`, `obras_instalacoes`, `equipe_executora`, `passagens`, `diarias`, `material_consumo_nacional`, `material_consumo_importado`, `servicos_terceiros`, `outros_bens_direitos`, `prototipo_nacional`, `prototipo_importado`, `outras_despesas`.

**Pare e pergunte** se um nome de aba/categoria da planilha não mapear claramente pra uma dessas 13 — nunca invente uma categoria nova nem force o mapeamento mais parecido sem confirmar.

## 4. Passo 2 — criar projeto e orçamento base

Com a API rodando (`HORUN_DEV_MODE=true` já dá `role="admin"` de graça, sem precisar de cabeçalho):

```
POST /projects                          {code, name, funding_agency, foundation}
POST /projects/{id}/revisions           {label: "Baseline SIGITEC", effective_date, note?}
POST /projects/{id}/revisions/{rid}/items   (uma vez por linha da aba de orçamento planejado)
  {category, item_number, description, justification, unit_value, planned_quantity, note?}
POST /projects/{id}/revisions/{rid}/activate
```

Se houver reformulações, repita `POST .../revisions` (que já clona os itens da revisão ativa) e então **edite** os itens clonados (`PATCH .../items/{item_id}`) pros valores da reformulação, em vez de recriar tudo do zero — mais fiel ao que a planilha real registra (a reformulação normalmente só ajusta valores existentes, raramente reescreve a lista inteira). Ative cada revisão em ordem cronológica antes de passar pra próxima.

Depois de criar os itens, confira: a soma por categoria bate com a coluna `C` (SIGITEC) do `Quadro Resumo` original? Se não bater, **pare** — é sinal de linha pulada ou категория mal mapeada, não de arredondamento.

## 5. Passo 3 — reconstruir os processos de compra a partir das pastas reais

Para cada linha de uma aba de execução (uma compra já realizada), o objetivo é criar um `PurchaseProcess` que termine no estado certo com os documentos reais anexados — não só o valor final numérico.

### 5.1 Localizar a pasta correspondente

A convenção observada no projeto original (pode variar — confirme antes de generalizar):

```
<Categoria>/Item <N> - <Descrição>/<Nº processo> - <Descrição>[ - CANCELADO]/
    1 - <arquivo>.pdf          <- cotação 1
    2 - <arquivo>.pdf          <- cotação 2 (concorrente)
    3 - <arquivo>.pdf          <- cotação 3
    <algo>COPPETEC<algo>.pdf   <- solicitação/proposta enviada à fundação
    autorizacao_de_fornecimento_<algo>.pdf   <- autorização emitida
    <NF|DANFE|Nota fiscal|BOLETO><algo>.pdf  <- nota fiscal/recibo
```

Casar pelo **número do item** (`Item <N>`) e, quando existir, pelo **Nº de Processo COPPETEC** da linha da planilha. Se uma linha da aba de execução não tiver pasta correspondente (ou vice-versa: uma pasta sem linha na planilha), **liste a divergência e pare** antes de importar em lote — não decida sozinho qual das duas fontes está certa.

### 5.2 Classificar os arquivos por tipo de documento

Heurística de nome de arquivo (ajustar conforme o que a pasta real mostrar):

| Padrão observado | `doc_type` |
|---|---|
| Prefixo numérico (`1 -`, `2 -`, `3 -`) em arquivo de proposta/orçamento/cotação | `cotacao` (máx. 3 por processo — se houver mais de 3 candidatos, escolha as 3 mais claramente "propostas de fornecedor concorrentes" e reporte as demais como `outro`) |
| Contém "COPPETEC" e parece uma solicitação/formulário de compra (não a autorização em si) | `solicitacao_autorizacao` |
| `autorizacao_de_fornecimento`, "autorização" | `solicitacao_autorizacao` (é a evidência mais próxima de autorização quando não há uma "solicitação" separada — ver nota abaixo) |
| `NF`, `DANFE`, "nota fiscal", `BOLETO` | `nota_fiscal` |
| Menciona "recebimento", "entrega", "recebido" | `comprovante_recebimento` |
| Qualquer outro (ex. e-mail impresso, ficha técnica) | `outro` — nunca descarte um arquivo real, só classifique como `outro` |

**Nota sobre autorização vs. solicitação**: o fluxo do módulo tem duas etapas (`solicitar_autorizacao` exige um documento `solicitacao_autorizacao` anexado; `autorizar` também). Muitas pastas reais só têm o documento de autorização final, não um registro separado do pedido enviado. Nesse caso, use o mesmo arquivo de autorização pra satisfazer o requisito de `solicitacao_autorizacao` (é a melhor evidência disponível de que a solicitação aconteceu) — mas **anote isso** (campo `note` do documento) como "documento de autorização reaproveitado — pasta não tinha registro separado da solicitação enviada", pra quem auditar depois entender a diferença entre um processo novo (que vai ter os dois documentos de verdade) e um importado.

### 5.3 Determinar o status final e replicar o fluxo

- Pasta com sufixo `- CANCELADO` → o processo deve terminar em `cancelado` (transição `cancelar`, com `reason` = alguma nota genérica tipo "importado do histórico — tentativa não concluída, ver pasta original").
- Pasta sem esse sufixo e com nota fiscal presente → o processo real já foi concluído. Replique as transições em ordem, anexando o documento real antes de cada uma (os guards do backend exigem isso — ver `backend/app/services/transitions.py`):
  ```
  POST .../purchase-processes                    {budget_position_id, title, quantity, estimated_unit_value, vendor?}
  POST .../purchase-processes/{pid}/documents     (cotação, se houver)
  POST .../purchase-processes/{pid}/transition    {action: "avancar_cotacao"}
  POST .../purchase-processes/{pid}/documents     (solicitação/autorização)
  POST .../purchase-processes/{pid}/transition    {action: "solicitar_autorizacao"}
  POST .../purchase-processes/{pid}/transition    {action: "autorizar", vendor}
  POST .../purchase-processes/{pid}/documents     (nota fiscal)
  POST .../purchase-processes/{pid}/transition    {action: "emitir_nota_fiscal", final_value}
  POST .../purchase-processes/{pid}/documents     (comprovante, se houver)
  POST .../purchase-processes/{pid}/transition    {action: "confirmar_recebimento"}
  POST .../purchase-processes/{pid}/transition    {action: "concluir"}
  ```
- **Se a pasta não tiver NENHUM documento do tipo `cotacao`** (comum em compras antigas/simples): a transição `avancar_cotacao` vai ser recusada pelo guard. Não contorne isso criando um documento falso — **pare e pergunte** ao usuário como tratar esse caso (opções reais: anexar o próprio documento de autorização também como `cotacao` com nota explicando, ou aceitar que esse processo específico fica registrado só como rascunho/dado incompleto, sinalizado pra revisão manual depois).
- `estimated_unit_value`/`quantity` vêm da linha da planilha; `final_value` na transição `emitir_nota_fiscal` deve ser o `Valor` real da aba de execução, não recalculado.

### 5.4 Conferência final por item

Depois de importar todas as linhas de uma categoria, chame `GET /projects/{id}/balance` e confira: o `realizado` do item bate com a soma dos valores da aba de execução daquele item na planilha original? Reporte qualquer item cujo saldo importado não reconcilie antes de seguir pra próxima categoria.

## 6. Passo 4 — Equipe Executora

Por linha da aba de pessoal:

```
POST /projects/{id}/personnel                         {full_name}
POST /projects/{id}/personnel-assignments              {person_id, budget_position_id, role_title, monthly_rate, start_date}
POST /projects/{id}/personnel-assignments/{aid}/close  {end_date}   (só se Situação = Encerrado)
```

O acúmulo (`accrued_value`) é sempre calculado pelo backend (`services/accrual.py`) a partir de `start_date`/`end_date`/`monthly_rate` — nunca envie um valor acumulado manualmente. Se a planilha mostrar um "Valor total" que não bate com o que o backend calcula depois de importado, o motivo típico é uma convenção de mês parcial diferente (a planilha original usa meses corridos por `DATE`/`YEAR`/`MONTH`, este módulo usa aniversário + fração de dias/30) — reporte a diferença ao usuário em vez de forçar os dois a baterem exatamente.

Se a pasta `Prestação de contas` (ou equivalente) tiver recibos por pessoa, anexe via `POST /personnel-assignments/{aid}/documents` (multipart, `period_label` no formato `AAAA-MM` quando der pra inferir do nome/data do arquivo).

## 7. Idempotência — reimportar sem duplicar

Antes de criar qualquer entidade, confira se ela já existe:

- `Project` — `GET /projects` e compare por `code` (é `unique` no banco; um segundo `POST` com o mesmo código dá `409`, use isso como sinal).
- `BudgetPosition`/`BudgetItem` — únicos por `(project_id, category, item_number)` dentro de uma revisão; se já existirem, prefira `PATCH` a duplicar.
- `PurchaseProcess`/`Document`/`PersonnelAssignment` — não têm chave natural própria contra a planilha. Se for rodar a importação uma segunda vez (reconciliação), **liste o que já existe primeiro** (`GET .../purchase-processes`, filtrando por `budget_position_id`) e decida junto com o usuário se um processo já importado deve ser pulado, atualizado ou se aquilo é uma tentativa nova de verdade.

## 8. Relatório antes de escrever

Antes do primeiro `POST` que grava dado de verdade (fora de um teste local descartável), produza um resumo pro usuário: quantos itens de orçamento, quantos processos de compra por status esperado, quantas pessoas/atribuições, e a lista de qualquer divergência/heurística incerta encontrada nos passos acima. Só prossiga pra escrita depois de confirmação explícita — mesma disciplina de "elicitação, não suposição" do resto do Horun.
