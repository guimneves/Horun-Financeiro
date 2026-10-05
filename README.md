# Horun · Financeiro

Módulo do **Projeto Horun**. Gerado a partir do template padrão — ver `../Prompt_Horun_Core.md` (arquitetura da plataforma) e `../Prompt_Horun_Modulo.md` (contrato completo de módulo).

## Estrutura

```
backend/    API FastAPI + SQLModel, própria deste módulo
frontend/   React + Vite + Tailwind, usa @horun/design-system para tema/identidade visual
MODULE.md   Manifesto lido pelo Horun Core (nome, ícone, porta, health check)
```

## Desenvolvendo de forma independente (sem o Horun Core rodando)

```
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
set HORUN_DEV_MODE=true
uvicorn app.main:app --reload

# frontend (outro terminal)
cd frontend
npm install
npm run dev
```

Com `HORUN_DEV_MODE=true`, o backend usa um usuário fixo (admin de desenvolvimento) em vez de exigir os cabeçalhos de identidade que só o Core injeta em produção — dá pra desenvolver e testar o módulo inteiro isolado.

## Plugando no Horun (quando estiver pronto)

1. Remover `HORUN_DEV_MODE` do ambiente de produção — o backend passa a exigir identidade vinda do Core.
2. Definir as variáveis de `.env.example` — em especial `MODULE_SECRET_KEY` (obrigatória fora do modo dev; o módulo não sobe sem ela) e `MODULE_COORDENADOR_PASSWORD` (senha mestra inicial de coordenador; não existe senha padrão).
3. Adicionar o serviço deste módulo ao `docker-compose.yml` do servidor (backend sem porta exposta ao host — só alcançável pelo Core, mesma regra do RE7S).
4. Cadastrar o módulo no painel de Administração do Core, a partir dos dados do `MODULE.md` (o cadastro é manual).

## Avisos por e-mail e no sininho (pelo Horun Core)

O módulo não guarda e-mails nem configura SMTP: pede ao Core, que cria o aviso
no sininho de cada pessoa (com link para dentro do módulo) e manda e-mail a quem
tem e-mail cadastrado e não desligou os e-mails em "Meu perfil". Código:
`backend/app/core/notify.py` (envio) e `backend/app/services/notifications.py`
(quais eventos, para quem).

| Evento | Quem recebe | Link |
|---|---|---|
| Compra enviada para autorização (**Solicitar autorização à COPPETEC**) | coordenadores do projeto | `/projects/{id}/purchases/{processo}` |
| Compra autorizada ou rejeitada | quem criou o processo | idem |
| Nota fiscal registrada acima do saldo do item (depois do aviso) | coordenadores do projeto | idem |

Quem fez a ação não recebe aviso dela. Os textos **não trazem valores em R$**
(o criador pode ser colaborador, que não vê valores, e o e-mail sai do
servidor) — o link leva à tela, onde cada um vê o que o seu papel permite.

**Para ligar:** o administrador gera a chave em Core → **Admin → Módulos →
Notificações** ("gerar chave"; o valor aparece uma vez) e, no servidor do
módulo, define `HORUN_CORE_URL=http://horun-core-backend:8000` e
`HORUN_NOTIFY_TOKEN=<chave>` (ver `.env.example`; o `docker-compose.yml` já
repassa as duas). Sem elas o módulo funciona igual, só sem avisos. O envio é em
segundo plano, com 5 s de limite; se o Core estiver fora do ar, só fica um
registro no log.
