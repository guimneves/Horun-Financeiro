"""Máquina de estado do PurchaseProcess — único ponto de entrada pra mudar
de status (em vez de uma rota por ação), pra garantir que nenhuma
transição passe sem checar seu guard. Ver Prompt_Encaixe_Juliana.md pro
fluxo real que isso modela: checar orçamento → cotação(ões) → autorização
COPPETEC → nota fiscal → comprovante de recebimento.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from sqlmodel import Session, select

from app.db.models.document import Document
from app.db.models.purchase import PurchaseProcess


class TransitionError(Exception):
    """Guard falhou ou a transição não é legal a partir do estado atual."""


def _count_docs(session: Session, process_id: int, doc_type: str) -> int:
    docs = session.exec(
        select(Document).where(
            Document.purchase_process_id == process_id,
            Document.doc_type == doc_type,
        )
    ).all()
    return len(docs)


def _guard_has_quote(session: Session, process: PurchaseProcess) -> None:
    if _count_docs(session, process.id, "cotacao") < 1:
        raise TransitionError("Anexe ao menos uma cotação antes de avançar.")


def _guard_has_authorization_doc(session: Session, process: PurchaseProcess) -> None:
    if _count_docs(session, process.id, "solicitacao_autorizacao") < 1:
        raise TransitionError("Anexe o documento de solicitação enviado à COPPETEC antes de autorizar.")


def _guard_has_invoice(session: Session, process: PurchaseProcess) -> None:
    if _count_docs(session, process.id, "nota_fiscal") < 1:
        raise TransitionError("Anexe a nota fiscal/recibo antes de avançar.")


def _guard_has_receipt(session: Session, process: PurchaseProcess) -> None:
    if _count_docs(session, process.id, "comprovante_recebimento") < 1:
        raise TransitionError("Anexe o comprovante de recebimento antes de avançar.")


@dataclass(frozen=True)
class TransitionRule:
    from_states: frozenset[str]
    to_state: str
    coordenador_only: bool
    guard: Callable[[Session, PurchaseProcess], None] | None = None
    requires_reason: bool = False
    requires_final_value: bool = False


_ALL_NON_TERMINAL = frozenset(
    {
        "verificacao_orcamento",
        "cotacao",
        "aguardando_autorizacao",
        "autorizado",
        "nota_fiscal_emitida",
        "comprovante_recebimento",
    }
)

TRANSITIONS: dict[str, TransitionRule] = {
    "avancar_cotacao": TransitionRule(frozenset({"verificacao_orcamento"}), "cotacao", False, _guard_has_quote),
    "solicitar_autorizacao": TransitionRule(frozenset({"cotacao"}), "aguardando_autorizacao", False, _guard_has_quote),
    "autorizar": TransitionRule(
        frozenset({"aguardando_autorizacao"}), "autorizado", True, _guard_has_authorization_doc
    ),
    "rejeitar": TransitionRule(frozenset({"aguardando_autorizacao"}), "rejeitado", True, requires_reason=True),
    "emitir_nota_fiscal": TransitionRule(
        frozenset({"autorizado"}), "nota_fiscal_emitida", False, _guard_has_invoice, requires_final_value=True
    ),
    "confirmar_recebimento": TransitionRule(
        frozenset({"nota_fiscal_emitida"}), "comprovante_recebimento", False, _guard_has_receipt
    ),
    "concluir": TransitionRule(frozenset({"comprovante_recebimento"}), "concluido", False),
    "cancelar": TransitionRule(_ALL_NON_TERMINAL, "cancelado", False, requires_reason=True),
}

# Cancelar continua aberto a qualquer membro ENQUANTO a compra ainda não foi
# autorizada (desistir de uma cotação é operacional, não uma decisão do
# coordenador) — mas uma vez autorizada, só o coordenador pode desfazer a
# própria decisão (ou o que veio depois dela).
_CANCELAR_REQUER_COORDENADOR_A_PARTIR_DE = frozenset(
    {"autorizado", "nota_fiscal_emitida", "comprovante_recebimento"}
)


def apply_transition(
    session: Session,
    process: PurchaseProcess,
    *,
    action: str,
    is_coordenador: bool,
    reason: str | None = None,
    vendor: str | None = None,
    process_number: str | None = None,
    final_value: Decimal | None = None,
) -> PurchaseProcess:
    from datetime import datetime, timezone

    rule = TRANSITIONS.get(action)
    if rule is None:
        raise TransitionError(f"Ação desconhecida: {action!r}.")
    if process.status not in rule.from_states:
        raise TransitionError(f"Não é possível '{action}' a partir do estado '{process.status}'.")
    requer_coordenador = rule.coordenador_only or (
        action == "cancelar" and process.status in _CANCELAR_REQUER_COORDENADOR_A_PARTIR_DE
    )
    if requer_coordenador and not is_coordenador:
        raise TransitionError("Ação restrita ao coordenador do projeto.")
    if rule.requires_reason and not reason:
        raise TransitionError("Informe o motivo.")
    if rule.requires_final_value and final_value is None:
        raise TransitionError("Informe o valor final da compra.")
    if rule.guard is not None:
        rule.guard(session, process)

    now = datetime.now(timezone.utc)

    if action == "autorizar":
        if vendor is not None:
            process.vendor = vendor
        if process_number is not None:
            process.process_number = process_number
        # estimated_value NÃO é editável aqui de propósito — o valor
        # "comprometido" tem que continuar rastreável até quantity ×
        # estimated_unit_value (editáveis via PATCH antes da autorização),
        # nunca um número solto vindo de uma transição.
    if action == "emitir_nota_fiscal":
        process.final_value = final_value
    if action in ("rejeitar", "cancelar"):
        process.cancel_reason = reason
        process.closed_at = now
    if action == "concluir":
        process.completed_at = now

    process.status = rule.to_state
    process.updated_at = now
    session.add(process)
    session.commit()
    session.refresh(process)
    return process
