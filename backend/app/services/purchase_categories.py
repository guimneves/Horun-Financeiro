"""Tipos de despesa liberados para compras (decisão dos coordenadores,
07/10/2026). Sem linha em ProjectPurchaseCategory = liberado, para os
projetos que já existiam não mudarem de comportamento."""

from __future__ import annotations

from sqlmodel import Session, select

from app.db.models.budget import EXPENSE_CATEGORIES, ProjectPurchaseCategory

PURCHASE_CLOSED_MESSAGE = (
    "Este tipo de despesa não está liberado para compras — um coordenador pode liberá-lo em Orçamento."
)


def category_rows(session: Session, project_id: int) -> dict[str, ProjectPurchaseCategory]:
    return {
        row.category: row
        for row in session.exec(
            select(ProjectPurchaseCategory).where(ProjectPurchaseCategory.project_id == project_id)
        )
    }


def is_category_open(session: Session, project_id: int, category: str) -> bool:
    """Equipe Executora nunca está "liberada": não usa o fluxo de compra."""
    if EXPENSE_CATEGORIES[category]["is_personnel"]:
        return False
    row = session.exec(
        select(ProjectPurchaseCategory).where(
            ProjectPurchaseCategory.project_id == project_id,
            ProjectPurchaseCategory.category == category,
        )
    ).first()
    return row is None or row.open
