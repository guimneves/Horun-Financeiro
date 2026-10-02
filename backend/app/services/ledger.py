"""Leitura dos lançamentos da planilha de acompanhamento de saldo — as abas
por categoria ("Equip. Nacional", "Material de Consumo"...), onde cada linha é
um processo com favorecido, descrição, valor e nº de processo COPPETEC.

As pastas dizem QUAIS processos existem; esta planilha diz QUANTO cada um
custou e quem foi o favorecido. O vínculo é o nº de processo (normalizado).

Linhas SEM nº de processo válido (DOA, ressarcimentos, passagens pela
agência, diárias — na planilha real a coluna do processo vem vazia, com uma
data ou com "?") também são despesas realizadas: a planilha as soma. Vêm em
`unnumbered`, com o nº do item, para entrarem como lançamentos sem nº.

As colunas são achadas pelo TÍTULO no cabeçalho (linha 2), não por posição:
umas abas têm a coluna "Quantidade" e outras não, o que desloca as demais.
Requer `openpyxl` (extra opcional `import`).
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.drive import fs_path
from app.core.process_number import normalize_process_number

# Nome da aba -> chave da categoria.
SHEET_CATEGORIES: dict[str, str] = {
    "Equip. Nacional": "equip_nacional",
    "Equip. Importado": "equip_importado",
    "Obras e Instalações": "obras_instalacoes",
    "Passagens": "passagens",
    "Diárias": "diarias",
    "Material de Consumo": "material_consumo_nacional",
    "Material de Consumo Importado": "material_consumo_importado",
    "Serv. Terceiros": "servicos_terceiros",
    "Outros Bens e Direitos": "outros_bens_direitos",
    "Protótipo Nacional": "prototipo_nacional",
    "Protótipo Importado": "prototipo_importado",
    "Outras Despesas": "outras_despesas",
}

_NUMBER_RE = re.compile(r"^\d{4}\D+\d+$")
_SUBITEM_RE = re.compile(r"^\s*(\d+)\s*[.,]\s*\d+\s*$")


def _item_number(raw: object) -> tuple[int | None, str | None]:
    """(nº do item, subitem como veio). O orçamento só tem itens inteiros: um
    subitem "1.1" (visto na planilha real, em Serviços) conta no item 1."""
    if isinstance(raw, bool):
        return None, None
    if isinstance(raw, int) or (isinstance(raw, float) and raw.is_integer()):
        return int(raw), None
    match = _SUBITEM_RE.match(str(raw)) if isinstance(raw, (str, float)) else None
    if match:
        return int(match.group(1)), str(raw).strip()
    return None, None


class LedgerError(Exception):
    pass


@dataclass
class LedgerEntry:
    process_number: str
    category: str
    item_number: int | None
    vendor: str | None
    description: str | None
    quantity: Decimal
    value: Decimal
    lines: int = 1  # quantas linhas da planilha foram somadas neste processo
    subitem: str | None = None  # "1.1": a planilha lança num subitem; entra no item 1


@dataclass
class UnnumberedEntry:
    """Linha de lançamento sem nº de processo COPPETEC."""

    ref: str  # identidade estável da linha (não duplica ao sincronizar de novo)
    category: str
    item_number: int
    sheet: str
    line: int
    vendor: str | None
    description: str | None
    quantity: Decimal
    value: Decimal
    raw_number: str  # o que estava na coluna do processo ("", "?", uma data...)
    on_date: date | None  # data da despesa, quando a coluna do processo trazia uma


@dataclass
class LedgerResult:
    entries: dict[str, LedgerEntry]
    skipped: list[str]  # linhas que não puderam ser usadas (sem valor, sem nº do item...)
    unnumbered: list[UnnumberedEntry] = field(default_factory=list)


def _line_ref(category: str, item: int, raw: str, vendor: object, description: object, value: Decimal, seen: dict[str, int]) -> str:
    # Pelo conteúdo, não pela posição: inserir uma linha na planilha não muda
    # a identidade das outras. Linhas idênticas ganham um nº de ordem.
    text = "|".join(str(x or "").strip().casefold() for x in (category, item, raw, vendor, description, value))
    seen[text] = seen.get(text, 0) + 1
    return hashlib.sha1(f"{text}#{seen[text]}".encode()).hexdigest()[:20]


def _as_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _find_columns(header: tuple[object, ...]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        text = str(cell or "").casefold()
        if "processo" in text:
            columns["process"] = index
        elif "nº do item" in text or "n° do item" in text or "no do item" in text:
            columns["item"] = index
        elif "quantidade" in text:
            columns["quantity"] = index
        elif "favorecido" in text:
            columns["vendor"] = index
        elif "descri" in text:
            columns["description"] = index
        elif text.strip() == "valor":
            columns["value"] = index
    return columns


def read_ledger(xlsx_path: str) -> LedgerResult:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise LedgerError("Instale o extra de importação (pip install -e '.[import]') para ler a planilha.") from exc

    if not os.path.isfile(fs_path(xlsx_path)):
        raise LedgerError(f"Planilha não encontrada: {xlsx_path}")

    try:
        workbook = openpyxl.load_workbook(fs_path(xlsx_path), data_only=True, read_only=True)
    except PermissionError as exc:
        # visto na prática: com a planilha aberta no Excel, o Windows trava o arquivo
        raise LedgerError(
            "Não foi possível abrir a planilha — ela está aberta no Excel? Feche-a e tente de novo."
        ) from exc
    except Exception as exc:  # zip corrompido, não é xlsx de verdade...
        raise LedgerError(f"Não foi possível abrir a planilha: {exc}") from exc
    entries: dict[str, LedgerEntry] = {}
    skipped: list[str] = []
    unnumbered: list[UnnumberedEntry] = []
    seen_lines: dict[str, int] = {}
    try:
        for sheet_name, category in SHEET_CATEGORIES.items():
            if sheet_name not in workbook.sheetnames:
                continue
            rows = workbook[sheet_name].iter_rows(min_row=2, max_col=12, values_only=True)
            header = next(rows, None)
            if header is None:
                continue
            columns = _find_columns(header)
            if "process" not in columns or "value" not in columns:
                skipped.append(f"{sheet_name}: cabeçalho sem 'Valor' ou 'Nº de Processo' — aba ignorada.")
                continue
            for line_number, row in enumerate(rows, start=3):

                def cell(key: str) -> object:
                    index = columns.get(key)
                    return row[index] if index is not None and index < len(row) else None

                raw_number = cell("process")
                value = _as_decimal(cell("value"))
                item_raw = cell("item")
                item_number, subitem = _item_number(item_raw)
                quantity = _as_decimal(cell("quantity")) or Decimal("1")
                raw_text = "" if raw_number is None else str(raw_number).strip()
                if not _NUMBER_RE.match(raw_text):
                    # sem nº de processo: ainda é despesa, se tem valor e item
                    if value is None or value == 0:
                        if raw_text:
                            skipped.append(f"{sheet_name} linha {line_number}: '{raw_text}' sem valor.")
                        continue
                    if item_number is None:
                        skipped.append(
                            f"{sheet_name} linha {line_number}: lançamento sem nº de processo"
                            + (f" ('{raw_text}')" if raw_text else "")
                            + f" e sem nº do item (valor {value}) — não dá para saber em que item lançar."
                        )
                        continue
                    on_date = raw_number.date() if isinstance(raw_number, datetime) else (
                        raw_number if isinstance(raw_number, date) else None
                    )
                    shown = on_date.isoformat() if on_date else raw_text
                    unnumbered.append(UnnumberedEntry(
                        ref=_line_ref(category, item_number, shown, cell("vendor"), cell("description"), value, seen_lines),
                        category=category,
                        item_number=item_number,
                        sheet=sheet_name,
                        line=line_number,
                        vendor=(str(cell("vendor")).strip() or None) if cell("vendor") else None,
                        description=(str(cell("description")).strip() or None) if cell("description") else None,
                        quantity=quantity,
                        value=value,
                        raw_number=shown,
                        on_date=on_date,
                    ))
                    continue
                if value is None:
                    skipped.append(f"{sheet_name} linha {line_number}: processo {raw_number} sem valor.")
                    continue
                number = normalize_process_number(raw_text)
                assert number is not None
                if number in entries:
                    existing = entries[number]
                    existing.value += value
                    existing.lines += 1
                else:
                    entries[number] = LedgerEntry(
                        process_number=number,
                        category=category,
                        item_number=item_number,
                        vendor=(str(cell("vendor")).strip() or None) if cell("vendor") else None,
                        description=(str(cell("description")).strip() or None) if cell("description") else None,
                        quantity=quantity,
                        value=value,
                        subitem=subitem,
                    )
    finally:
        workbook.close()
    return LedgerResult(entries=entries, skipped=skipped, unnumbered=unnumbered)
