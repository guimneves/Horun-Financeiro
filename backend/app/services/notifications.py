"""Quais eventos do Financeiro viram aviso (sininho + e-mail) e para quem.

Só o que pede ação de alguém ou o que alguém está esperando — não cada
clique. Destinatários são ids do Core (`ProjectMembership.user_id` e
`PurchaseProcess.created_by_user_id` vêm do cabeçalho X-Horun-User-Id); quem
fez a ação nunca é avisado da própria ação.

Os textos NUNCA levam valores em R$: o criador de um processo pode ser
colaborador (que não vê valores no módulo), e o e-mail sai do servidor. O
link leva à tela, onde cada um vê o que o seu papel permite.

| Evento                                   | Quem recebe                     |
|------------------------------------------|---------------------------------|
| compra enviada para autorização          | coordenadores do projeto        |
| compra autorizada / rejeitada            | quem criou o processo           |
| nota fiscal registrada acima do saldo    | coordenadores do projeto        |
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core import notify as notify_module
from app.core.identity import HorunIdentity
from app.db.models.budget import BudgetPosition
from app.db.models.project import Project, ProjectMembership
from app.db.models.purchase import PurchaseProcess


def process_link(process: PurchaseProcess) -> str:
    return f"/projects/{process.project_id}/purchases/{process.id}"


def coordinator_ids(session: Session, project_id: int) -> list[str]:
    return list(
        session.exec(
            select(ProjectMembership.user_id).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.role == "coordenador",
            )
        )
    )


def _without_actor(user_ids: list[str], actor: HorunIdentity | None) -> list[str]:
    return [uid for uid in user_ids if actor is None or uid != actor.user_id]


def _describe(session: Session, process: PurchaseProcess) -> str:
    project = session.get(Project, process.project_id)
    position = session.get(BudgetPosition, process.budget_position_id)
    where = f"projeto {project.code} — {project.name}" if project else "projeto"
    item = f", item Nº {position.item_number}" if position is not None else ""
    number = f" (processo {process.process_number})" if process.process_number else ""
    return f"\"{process.title}\"{number} — {where}{item}"


def notify_transition(
    session: Session,
    process: PurchaseProcess,
    *,
    action: str,
    actor: HorunIdentity | None,
    reason: str | None = None,
    over_balance: bool = False,
) -> None:
    """Chamado depois que a transição foi gravada (rota de transição)."""
    who = actor.username if actor else "alguém"
    link = process_link(process)

    if action == "solicitar_autorizacao":
        recipients = _without_actor(coordinator_ids(session, process.project_id), actor)
        notify_module.notify(
            "Compra aguardando autorização",
            f"{who} enviou a compra {_describe(session, process)} para autorização.\n\n"
            "Abra o processo para conferir os documentos e clicar em \"Autorizar compra\" ou \"Rejeitar\".",
            link,
            user_ids=recipients,
        )
    elif action in ("autorizar", "rejeitar"):
        recipients = _without_actor([process.created_by_user_id], actor)
        if action == "autorizar":
            subject = "Compra autorizada"
            text = (
                f"A compra {_describe(session, process)} foi autorizada por {who}.\n\n"
                "Próximo passo: quando a nota fiscal chegar, anexe-a no processo e clique em \"Registrar nota fiscal\"."
            )
        else:
            subject = "Compra rejeitada"
            text = (
                f"A compra {_describe(session, process)} foi rejeitada por {who}."
                + (f"\nMotivo: {reason}" if reason else "")
                + "\n\nSe ainda for preciso comprar, abra um novo processo de compra."
            )
        notify_module.notify(subject, text, link, user_ids=recipients)
    elif action == "emitir_nota_fiscal" and over_balance:
        recipients = _without_actor(coordinator_ids(session, process.project_id), actor)
        notify_module.notify(
            "Nota fiscal acima do saldo do item",
            f"{who} registrou a nota fiscal da compra {_describe(session, process)} com valor acima do saldo "
            "do item (confirmado depois do aviso).\n\n"
            "Abra o processo e o Orçamento para ver os valores e decidir se o item precisa de remanejamento.",
            link,
            user_ids=recipients,
        )
