"""Nº de processo COPPETEC — no mundo real aparece de vários jeitos: "2024 3708"
(planilha), "2024-5616" (nome de pasta), "2024_5616"... A forma canônica
guardada e comparada é "AAAA-N" (ano, hífen, número sem zeros à esquerda).
"""

from __future__ import annotations

import re

_PATTERN = re.compile(r"(\d{4})\D+0*(\d+)")


def normalize_process_number(value: str | None) -> str | None:
    """Devolve "AAAA-N". Se o texto não parece um nº de processo, devolve o
    texto como veio (sem espaços nas pontas) — nada é descartado em silêncio.
    Vazio vira None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = _PATTERN.search(text)
    if match is None:
        return text
    return f"{match.group(1)}-{int(match.group(2))}"
