"""Orçamento: posição estável do item, revisões (reformulações) e o valor
planejado de cada item dentro de uma revisão específica.

Separar `BudgetPosition` (identidade — "Item Nº X da categoria Y") de
`BudgetItem` (o valor daquele item numa revisão específica) deixa o
histórico de reformulações inteiro navegável — uma reformulação nova clona
os valores da revisão ativa em `BudgetItem`s novos, sem apagar os antigos,
e `PurchaseProcess`/`PersonnelAssignment` (Milestone 2/3) referenciam a
posição (estável a vida toda do projeto), nunca uma revisão específica.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Categorias fixas — string plana, não enum nativo do banco (mesma
# convenção do Horun Core: ver POSITIONS/QUALIFICATIONS em
# Horun Core/backend/app/db/models.py). "is_personnel" marca a única
# categoria que não segue o fluxo de compra (Equipe Executora, Milestone 3).
EXPENSE_CATEGORIES: dict[str, dict[str, object]] = {
    "equip_nacional": {"label": "Equipamento e Material Permanente — Nacional", "group": "capital", "is_personnel": False},
    "equip_importado": {"label": "Equipamento e Material Permanente — Importado", "group": "capital", "is_personnel": False},
    "obras_instalacoes": {"label": "Obras e Instalações", "group": "capital", "is_personnel": False},
    "equipe_executora": {"label": "Equipe Executora", "group": "corrente", "is_personnel": True},
    "passagens": {"label": "Passagens", "group": "corrente", "is_personnel": False},
    "diarias": {"label": "Diárias / Ajuda de Custo", "group": "corrente", "is_personnel": False},
    "material_consumo_nacional": {"label": "Material de Consumo — Nacional", "group": "corrente", "is_personnel": False},
    "material_consumo_importado": {"label": "Material de Consumo — Importado", "group": "corrente", "is_personnel": False},
    "servicos_terceiros": {"label": "Serviços de Terceiros", "group": "corrente", "is_personnel": False},
    "outros_bens_direitos": {"label": "Outros Bens e Direitos", "group": "corrente", "is_personnel": False},
    "prototipo_nacional": {"label": "Protótipo ou Unidade Piloto — Nacional", "group": "corrente", "is_personnel": False},
    "prototipo_importado": {"label": "Protótipo ou Unidade Piloto — Importado", "group": "corrente", "is_personnel": False},
    "outras_despesas": {"label": "Outras Despesas", "group": "corrente", "is_personnel": False},
}


class BudgetPosition(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("project_id", "category", "item_number", name="uq_position_project_category_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    category: str = Field(index=True)  # chave de EXPENSE_CATEGORIES
    item_number: int  # "Nº" da planilha, único dentro da categoria
    created_at: datetime = Field(default_factory=_utcnow)


class BudgetRevision(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("project_id", "revision_number", name="uq_revision_project_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    revision_number: int  # 0 = baseline (SIGITEC), 1/2/3... = "Reformulação Nº1/2/3"
    label: str  # "Baseline SIGITEC", "Reformulação Nº1"
    status: str = "rascunho"  # rascunho | ativa | substituida
    effective_date: date
    note: str = ""
    created_by_user_id: str
    created_by_username: str
    created_at: datetime = Field(default_factory=_utcnow)


class BudgetItem(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("revision_id", "position_id", name="uq_item_revision_position"),
    )

    id: int | None = Field(default=None, primary_key=True)
    revision_id: int = Field(foreign_key="budgetrevision.id", index=True)
    position_id: int = Field(foreign_key="budgetposition.id", index=True)
    description: str  # Descrição do item
    justification: str = ""  # Finalidade/Justificativa
    unit_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))  # V. unitário (ou valor mensal, p/ pessoal)
    planned_quantity: Decimal = Field(sa_column=Column(Numeric(14, 2)))  # Quant. Prevista
    planned_value: Decimal = Field(sa_column=Column(Numeric(14, 2)))  # Valor (R$) = unit_value * planned_quantity
    yield_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(14, 2)))  # Rendimentos
    note: str = ""  # ex. valor original em moeda estrangeira
    created_at: datetime = Field(default_factory=_utcnow)
