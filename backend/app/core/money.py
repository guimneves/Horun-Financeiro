"""Tipos de entrada para dinheiro e quantidade, alinhados às colunas
`Numeric(14, 2)` do banco.

Sem isto, a API aceitava qualquer `Decimal`: um colaborador criava um
processo com quantidade negativa, o "comprometido" do item diminuía e
liberava saldo que a política "bloquear" deveria negar (`check_balance` só
olha aumentos). E valores com mais de 2 casas eram devolvidos de um jeito e
gravados de outro (o banco arredonda).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import Field

CENTS = Decimal("0.01")

# Valor em R$: nunca negativo (zero é válido — ex. processo importado do drive
# sem valor na planilha).
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
# Quantidade de um processo de compra: tem que existir algo sendo comprado.
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
# Quantidade prevista no orçamento: zero é aceito (item reservado na revisão).
NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


def round_money(value: Decimal) -> Decimal:
    """Arredonda para centavos (meio para cima, como a planilha). Usado em
    todo valor CALCULADO (quantidade × unitário), que pode ter 4 casas."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def reject_null(value: object) -> object:
    """Validador para campos opcionais de PATCH que não podem ser LIMPOS.

    `None` como padrão significa "não mexer" (o campo nem chega na rota por
    causa do `exclude_unset`). Mas um `null` explícito no JSON passava e
    virava `None` no modelo — 500 na conta (`None * Decimal`) ou violação de
    NOT NULL no commit. O Pydantic só roda o validador em valor enviado, então
    o padrão continua valendo."""
    if value is None:
        raise ValueError("não pode ser vazio")
    return value
