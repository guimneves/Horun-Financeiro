# Implantação do Financeiro no Horun (servidor + Horun Agent)

Três máquinas/papéis:

| Onde | O que roda |
|---|---|
| **Servidor do laboratório** (onde já rodam o Core e o RE7S) | `docker compose` deste repositório: banco, backup, backend e frontend |
| **PC onde o OneDrive sincroniza** a pasta dos projetos | **Horun Agent** — lê a pasta e entrega ao servidor; o PC não abre porta nenhuma |
| **Seu PC de testes** | continua com o `Apresentar_Financeiro.bat` (modo local, base própria em `C:\HorunDemo\Financeiro`) — não interfere no servidor |

Ordem: 1 → 2 → 3 → 4 → 5. Os valores entre `<...>` são seus; nada disso vai para o GitHub.

## 1. Servidor: subir o módulo

```powershell
cd C:\Horun                      # mesma pasta onde estão Horun-Core e RE7S-Horun
git clone https://github.com/guimneves/Horun-Financeiro.git
cd Horun-Financeiro
copy .env.example .env
notepad .env
```

No `.env`, preencha:

- `POSTGRES_PASSWORD` — uma senha forte qualquer (fica só aqui).
- `MODULE_SECRET_KEY` — gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `MODULE_COORDENADOR_PASSWORD` — a senha mestra inicial de coordenador.
- `BACKUP_DIR` — uma pasta do Windows fora do Docker (ex. `C:/HorunBackups/financeiro`).
- Deixe `MODULE_DRIVE_MODE=agent` e `MODULE_DRIVE_AGENT_ROOT=financeiro`.
- `MODULE_DRIVE_WRITE=true` se os documentos anexados no Financeiro devem ir
  também para a pasta do processo no drive (exige `"mode": "read-write"` no
  agente, passo 4). `MODULE_DRIVE_AUTO_SYNC_MINUTES` (padrão 30) é o intervalo
  da sincronização automática; `0` desliga.

```powershell
docker compose up -d --build
docker compose ps                # financeiro-backend e financeiro-frontend "healthy"
```

Libere a porta do agente no firewall do servidor (uma vez, PowerShell como administrador):

```powershell
New-NetFirewallRule -DisplayName "Horun Financeiro - agente (8002)" -Direction Inbound -Protocol TCP -LocalPort 8002 -Action Allow
```

Conferência da porta estreita (de qualquer PC da rede): `curl http://<IP do servidor>:8002/agent/enroll-codes` deve responder **404**.

## 2. Core: cadastrar o módulo

Horun → **Admin → Módulos → Cadastrar módulo**:

- Id: `financeiro` · Nome público: `Financeiro`
- URL interna (backend): `http://financeiro-backend:8000`
- URL interna (frontend): `http://financeiro-frontend:80`

Depois, em **Permissões**, libere o módulo para quem vai usar (coordenadores do
Core já veem todos os módulos). Opcional: **Notificações → gerar chave** e
colocar `HORUN_NOTIFY_TOKEN=<chave>` no `.env` do Financeiro
(`docker compose up -d` de novo).

Abra o módulo pela barra lateral: deve carregar a lista de projetos (vazia).

## 3. Código de instalação do agente

No Financeiro, aba **Organização** → painel do Horun Agent → **Gerar código de instalação**.
O código vale 60 minutos e serve uma vez.

## 4. PC do OneDrive: instalar o Horun Agent

Fora do OneDrive (para o próprio agente não ficar sincronizando):

```powershell
mkdir C:\Horun; cd C:\Horun
git clone https://github.com/guimneves/Agent-Horun.git
cd Agent-Horun
python -m venv .venv
.venv\Scripts\pip install -e .
copy config.example.json config.json
notepad config.json
```

`config.json` (troque o caminho pela pasta que **contém** as pastas dos projetos):

```json
{
  "device_name": "PC-ONEDRIVE-FINANCEIRO",
  "poll_interval_seconds": 3,
  "servers": [
    {
      "url": "http://<IP do servidor>:8002",
      "enroll_code": "<código do passo 3>",
      "device_token": "",
      "roots": {
        "financeiro": { "path": "C:\\Users\\<usuário>\\OneDrive - IQ-UFRJ (1)\\Doutorado\\Programas\\Maturação artificial", "mode": "read" }
      }
    }
  ]
}
```

- O nome `financeiro` tem que ser igual a `MODULE_DRIVE_AGENT_ROOT` do servidor.
- `"mode": "read"` — o Financeiro só lê o drive; o agente recusa qualquer escrita.
- `"mode": "read-write"` — necessário com `MODULE_DRIVE_WRITE=true`: o Financeiro
  grava os anexos na pasta de cada processo e renomeia a pasta "SEM NUMERO ..."
  quando o nº chega. Ele nunca sobrescreve nem apaga arquivos.
- Se este PC já tem um agente para outro módulo, **não instale outro**: acrescente
  este bloco em `servers` do `config.json` existente e reinicie o agente.

Iniciar automaticamente a cada login (janela aberta, como no PC do Rock-Eval):
siga `install/README.md` do Agent-Horun, opção **A** (atalho `.bat` na pasta
Inicializar). Na primeira execução o agente troca o código pelo token (o
`device_token` aparece preenchido no `config.json`).

Cuidados: o PC não pode suspender; no OneDrive, marque a pasta dos projetos como
**"Sempre manter neste dispositivo"** (arquivo só na nuvem não é lido); desligue
o "Modo de Edição Rápida" da janela do agente.

Conferência: em **Organização**, a instalação aparece com o "visto por último"
de poucos segundos atrás; na aba **Drive** do projeto, **Verificar de novo** não
acusa agente desligado.

## 5. Carregar o projeto

No Financeiro (pelo Horun):

1. **+ Novo projeto** (código, nome, vigência).
2. **Revisões → Importar orçamento da planilha** (envie a planilha de acompanhamento) e ative a revisão.
3. **Equipe → Importar equipe da planilha** (a mesma planilha).
4. **Configurações → pasta do drive**: o nome da pasta do projeto dentro de
   "Maturação artificial".
5. **Drive → Ler pastas → Sincronizar** (a planilha de "0_Saldo por item" é achada sozinha).
6. **Configurações → parcelas** e membros do projeto.

## Atualizar depois

```powershell
cd C:\Horun\Horun-Financeiro
git pull
docker compose up -d --build
```

O banco e os documentos ficam nos volumes `financeiro_pgdata` e
`financeiro_uploads` (sobrevivem ao rebuild; só somem com `docker compose down -v`).
