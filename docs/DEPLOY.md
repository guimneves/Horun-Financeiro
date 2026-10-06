# Financeiro no Horun — passo a passo

Guia para instalar o Financeiro no Horun e mostrar a importação de um projeto.
Os comandos são copiados e colados no **PowerShell** (a janela azul/preta de
comandos do Windows). Onde aparece `<...>`, troque pelo seu valor — e esses
valores (senhas, códigos) **nunca** vão para o GitHub nem para mensagens.

## Como as peças se encaixam

| Peça | Onde fica | Para que serve |
|---|---|---|
| **Financeiro** | no servidor do laboratório, junto com o Horun e os outros módulos | as telas, os cálculos e o banco de dados |
| **Pasta dos projetos** | num computador do laboratório | as pastas de cada projeto, com a planilha de acompanhamento e os PDFs de cada compra |
| **Leitor de pastas** (chamado de "Horun Agent") | no mesmo computador da pasta | um programinha que entrega ao Financeiro o que está na pasta, quando o Financeiro pede |

O servidor não enxerga o disco dos outros computadores. Por isso existe o
leitor de pastas: ele roda no computador da pasta, fica perguntando ao servidor
"precisa de alguma coisa?" e responde com a lista de pastas ou o arquivo pedido.
Esse computador não precisa liberar nada na rede — é sempre ele quem chama o servidor.

**Por enquanto:** a pasta dos projetos é uma **cópia** baixada para o seu
computador, e o leitor vai rodar nele. Quando decidirmos o computador
definitivo (o que fica sempre ligado e sincroniza o OneDrive), o leitor é
instalado lá do mesmo jeito, só trocando o endereço da pasta.

Para testar coisas novas sem mexer no servidor, continue usando o
`Apresentar_Financeiro.bat` no seu computador: ele tem dados próprios e lê a
pasta direto, sem o leitor.

---

## Parte 1 — Instalar o Financeiro no servidor (já feito em 06/10/2026)

No servidor, a pasta `C:\Horun` guarda o Horun e cada módulo, lado a lado:
`Horun-Core`, `Horun-RE7S`, `Horun-Financeiro`, `Horun-Reagentes`, `Horun-Amostras`.

1. **Baixar o Financeiro do GitHub:**

   ```powershell
   cd C:\Horun
   git clone https://github.com/guimneves/Horun-Financeiro.git
   cd Horun-Financeiro
   ```

2. **Criar o arquivo de configuração** (`.env`). Ele guarda as senhas deste
   servidor e nunca sai dele.

   ```powershell
   copy .env.example .env
   mkdir C:\HorunBackups\financeiro
   notepad .env
   ```

   Preencha três linhas:
   - `POSTGRES_PASSWORD` — senha do banco de dados;
   - `MODULE_SECRET_KEY` — uma chave secreta;
   - `MODULE_COORDENADOR_PASSWORD` — a senha mestra de coordenador do Financeiro (você escolhe).

   Para as duas primeiras, gere valores aleatórios com o comando abaixo (rode
   uma vez para cada, copie o resultado direto para o arquivo, não envie a ninguém):

   ```powershell
   $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | % { $_.ToString('x2') })
   ```

3. **Ligar o Financeiro:**

   ```powershell
   docker compose up -d --build
   docker compose ps
   ```

   Na primeira vez leva alguns minutos. No fim, as quatro linhas devem dizer
   **Up**, e as de `backend`, `frontend` e `db` também **(healthy)**.

4. **Abrir a passagem do leitor de pastas** no firewall do servidor (PowerShell
   aberto **como administrador**, uma vez só):

   ```powershell
   New-NetFirewallRule -DisplayName "Horun Financeiro - agente (8002)" -Direction Inbound -Protocol TCP -LocalPort 8002 -Action Allow
   ```

   Essa passagem (a "porta 8002") só aceita os pedidos do leitor de pastas.
   Para conferir, de outro computador:
   `curl.exe -i http://192.168.31.80:8002/agent/enroll-codes` → a resposta tem
   que começar com **404** (quer dizer: aberta, e sem mostrar nada indevido).

**Os dados ficam guardados mesmo se o Financeiro for desligado ou atualizado.**
Só **nunca** use `docker compose down -v` — o `-v` apaga os dados.

## Parte 2 — Colocar o Financeiro no menu do Horun (já feito)

No Horun: **Admin → Módulos → Cadastrar módulo**

| Campo | Valor |
|---|---|
| Id | `financeiro` |
| Nome público | `Financeiro` |
| URL interna (backend) | `http://financeiro-backend:8000` |
| URL interna (frontend) | `http://financeiro-frontend:80` |

Atenção ao **8000** — o 8002 é só do leitor de pastas; com 8002 aqui o módulo
aparece "fora do ar". Para corrigir depois, use **editar** ao lado do nome.

Em **Admin → Permissões**, libere o Financeiro para quem vai usar (coordenadores
do Horun já veem todos os módulos).

## Parte 3 — Preparar a pasta dos projetos

Escolha uma pasta no computador onde o leitor vai rodar (por enquanto, o seu),
por exemplo `C:\FinanceiroDrive`. Dentro dela, **uma pasta por projeto**,
organizada como no OneDrive:

```
C:\FinanceiroDrive\
   <pasta do projeto>\
      0_Saldo por item\            ← a planilha de acompanhamento ("... Acompanhamento de saldo ...xlsx")
      Material de consumo - Nacional\
         Item 1 - <descrição>\
            2024-1234 <título>\    ← uma pasta por compra: nº do processo COPPETEC + título
               cotação, autorização, nota fiscal... (PDFs)
      Equipamento e Material Permanente - Nacional\
      Serviço\
      ...
```

O que o Financeiro reconhece sozinho:
- **Categorias** pelo nome da pasta (as mesmas da planilha: Material de consumo, Equipamento, Serviço, Protótipo, Obras, Outros bens...).
- **Itens** pelas pastas `Item N - descrição`.
- **Compras** pelas pastas que começam com o nº do processo (`2024-1234`, `2024 1234`...). "(CANCELADO)" no nome = compra cancelada.
- **Tipo de cada PDF** pelo nome (autorização de fornecimento, nota fiscal, cotação/proposta, boleto...).
- **Valores** pela planilha de acompanhamento (a de "0_Saldo por item"), inclusive lançamentos sem nº de processo (DOA, ressarcimentos, passagens).

Pastas fora desse padrão aparecem numa lista de "não reconhecidas" na hora de
ler — nada é perdido nem alterado.

**Projetos novos podem ter diferenças** (nomes de pastas ou de abas da planilha
diferentes). Teste cada projeto novo primeiro no `Apresentar_Financeiro.bat`;
se algo não for reconhecido, mande os avisos da tela (sem valores) para ajustarmos.

## Parte 4 — Ligar o leitor de pastas no computador da pasta

**4.1 Pedir um código de instalação.** No Horun, abra o Financeiro → aba
**Organização** → **Gerar código de instalação**. O código vale 60 minutos e
serve uma vez só.

**4.2 Instalar o leitor** (no computador da pasta, fora do OneDrive):

```powershell
mkdir C:\Horun; cd C:\Horun
git clone https://github.com/guimneves/Agent-Horun.git
cd Agent-Horun
python -m venv .venv
.venv\Scripts\pip install -e .
copy config.example.json config.json
notepad config.json
```

**4.3 Dizer ao leitor onde está o servidor e qual pasta ele pode ler.** Apague
o conteúdo do `config.json` e cole este, trocando as duas partes marcadas:

```json
{
  "device_name": "PC-PASTA-FINANCEIRO",
  "poll_interval_seconds": 3,
  "servers": [
    {
      "url": "http://192.168.31.80:8002",
      "enroll_code": "<código do passo 4.1>",
      "device_token": "",
      "roots": {
        "financeiro": { "path": "C:\\FinanceiroDrive", "mode": "read" }
      }
    }
  ]
}
```

- No caminho da pasta, use **duas barras** (`C:\\FinanceiroDrive`).
- `"mode": "read"` = o leitor **só lê**: ele se recusa a gravar, apagar ou mover qualquer coisa.
- Se este computador já tem um leitor para outro módulo (como o do Rock-Eval),
  **não instale outro**: acrescente este bloco na lista `servers` do
  `config.json` que já existe.

**4.4 Fazer o leitor abrir sozinho** sempre que o Windows iniciar (cria um
atalho na pasta "Inicializar"):

```powershell
$bat = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Horun Agent.bat"
Set-Content -Path $bat -Encoding ascii -Value @'
@echo off
title Horun Agent - NAO FECHE ESTA JANELA
cd /d C:\Horun\Agent-Horun
.venv\Scripts\python.exe -m agent
pause
'@
```

Dê dois cliques nesse atalho para ligar agora. Uma janela preta abre e deve
ficar aberta — fechar a janela desliga o leitor.

Na primeira vez, o leitor troca o código por uma "chave" permanente (o campo
`device_token` do `config.json` aparece preenchido e o código some).

**Cuidados:**
- O computador **não pode entrar em suspensão** (Configurações → Sistema →
  Energia → Suspender: Nunca). Desligar só a tela não tem problema.
- Na janela do leitor: botão direito na barra de título → **Propriedades** →
  desmarque **"Modo de Edição Rápida"**. Com ele ligado, um clique dentro da
  janela **congela** o leitor até alguém apertar Enter.
- Se a pasta estiver no OneDrive, marque-a como **"Sempre manter neste
  dispositivo"** (arquivo que está só na nuvem não é lido).

**4.5 Conferir.** No Financeiro → **Organização**, o computador aparece na
lista com "visto por último" de poucos segundos atrás.

## Parte 5 — Importar um projeto (o roteiro para demonstrar)

No Financeiro, pelo Horun:

1. **+ Novo projeto** — código, nome e datas de início e fim.
2. **Revisões → Importar orçamento da planilha** — envie a planilha de
   acompanhamento do projeto. Confira a prévia e clique para importar; depois,
   **ative** a revisão.
3. **Equipe → Importar equipe da planilha** — a mesma planilha.
4. **Configurações → Pasta do drive** — o nome da pasta do projeto (só o nome,
   ex. `<pasta do projeto>`, não o caminho inteiro).
5. **Drive → Ler pastas** — o Financeiro mostra o que encontrou: compras a
   criar, valores a preencher, pastas não reconhecidas. Nada é gravado ainda.
6. **Sincronizar** — agora sim cria as compras e liga os PDFs a cada uma.
7. **Configurações → Parcelas** e a aba **Membros** (quem participa do projeto).
8. Abra o **Resumo** para mostrar o resultado.

A planilha de "0_Saldo por item" é encontrada sozinha (deixe o campo vazio).
Feche a planilha no Excel antes de sincronizar — aberta, o Windows não deixa ler.

## Atualizar o Financeiro depois

No servidor:

```powershell
cd C:\Horun\Horun-Financeiro
git pull
docker compose up -d --build
```

O Financeiro fica fora do ar por um ou dois minutos; os dados continuam.

## Se algo der errado

| O que aparece | O que fazer |
|---|---|
| Financeiro "fora do ar" no Horun | Admin → Módulos → **editar**: a URL do backend tem que ser `http://financeiro-backend:8000` |
| "Agente desligado" / Drive não responde | a janela do leitor está aberta no computador da pasta? O computador está ligado e sem suspender? |
| Erro ao ler a planilha | a planilha está aberta no Excel — feche e tente de novo |
| Pastas "não reconhecidas" | o nome não segue o padrão da Parte 3 — renomeie na cópia ou mande o aviso para ajustarmos |
| Qualquer outra coisa | no servidor, na pasta do Financeiro: `docker compose logs --tail 30 financeiro-backend` e mande o resultado |
