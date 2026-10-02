"""Um só lugar pra decidir "colaborador vê o número ou só a
disponibilidade" — usado por toda rota que serializa valor monetário.
`visible` normalmente é `membership.role == "coordenador"` (que já
considera a sessão elevada pela senha mestra, ver core/permissions.py)."""

from __future__ import annotations

from decimal import Decimal


def money(value: Decimal | None, *, visible: bool) -> Decimal | None:
    return value if visible else None
