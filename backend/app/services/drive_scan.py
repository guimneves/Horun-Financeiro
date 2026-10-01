"""Leitura da estrutura de pastas do projeto no drive — SOMENTE leitura, e só
nomes e tamanhos (não abre o conteúdo dos arquivos: no OneDrive isso baixaria
cada PDF).

Estrutura esperada (a que o laboratório já usa):

  <pasta do projeto>/
    <Categoria>/                      ex. "Material de consumo - Nacional"
      Item <N> - <descrição>/         ex. "Item 14 - Colunas cromatográficas"
        <AAAA>[ -_]<NNNN> <título>/   ex. "2024-10098 Tubo inox"
          arquivos (PDF...)           pasta marcada "(CANCELADO)" = tentativa cancelada

O que não segue esse padrão (viagens, reformulações, diárias por pessoa...) não
é forçado a virar processo: vai para `unrecognized`, com o motivo, para a
pessoa decidir.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field

from app.core.drive import fs_path
from app.core.process_number import normalize_process_number

# Nome da pasta de categoria (sem acento, minúsculo) -> chave em EXPENSE_CATEGORIES.
CATEGORY_FOLDERS: dict[str, str] = {
    "equipamento e material permanente - nacional": "equip_nacional",
    "equipamento e material permanente - importado": "equip_importado",
    "obras e instalacoes": "obras_instalacoes",
    "passagens": "passagens",
    "diarias": "diarias",
    "ajuda de custo": "diarias",
    "material de consumo - nacional": "material_consumo_nacional",
    "material de consumo - importado": "material_consumo_importado",
    "servico": "servicos_terceiros",
    "servicos": "servicos_terceiros",
    "servicos de terceiros": "servicos_terceiros",
    "outros bens e direitos": "outros_bens_direitos",
    "prototipo ou unidade piloto - nacional": "prototipo_nacional",
    "prototipo ou unidade piloto - importado": "prototipo_importado",
    "outras despesas": "outras_despesas",
}
PERSONNEL_FOLDERS = {"equipe executora"}

_ITEM_RE = re.compile(r"^Item\s+0*(\d+)\s*[-–—]\s*(.*)$", re.IGNORECASE)
_PROCESS_RE = re.compile(r"^(\d{4})[\s\-_]+(\d+)(.*)$")
_CANCELLED_RE = re.compile(r"[\(\[]?\s*\bcancelad[oa]\b\s*[\)\]]?", re.IGNORECASE)
_IGNORED_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}


def fold(text: str) -> str:
    """Minúsculo, sem acento, `_` e travessões viram espaço/hífen — para comparar nomes."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace("_", " ").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def classify_document(filename: str) -> str:
    """Tipo do documento pelo nome do arquivo (heurística; o usuário pode corrigir)."""
    name = fold(os.path.splitext(filename)[0])
    if "autorizacao de fornecimento" in name:
        return "autorizacao_fornecimento"
    if "boleto" in name or name.startswith("bol "):
        return "boleto"
    if re.search(r"(?<![a-z])(nf|nfe|nfse|danfe)", name) or re.search(r"\bnota|atestad", name):
        return "nota_fiscal"
    if "importacao" in name:
        return "pedido_importacao"
    if (
        "cotac" in name
        or "orcamento" in name
        or "proposta" in name
        or "proforma" in name
        # As cotações costumam ser numeradas "1 - ...", "2 - ...", "3 - ..." e
        # as propostas de fornecedor vêm endereçadas à fundação.
        or re.match(r"^[1-3]\s*-\s", name)
        or "coppetec" in name
        or "fundacao coordenacao" in name
    ):
        return "cotacao"
    return "outro"


@dataclass
class ScannedFile:
    rel_path: str  # relativo à pasta do projeto, com "/"
    name: str
    size_bytes: int
    doc_type: str


@dataclass
class ScannedProcess:
    category: str
    item_number: int
    item_folder: str  # rel_path da pasta do item
    folder: str  # rel_path da pasta do processo
    process_number: str  # normalizado "AAAA-N"
    title: str
    cancelled: bool
    inferred_status: str
    files: list[ScannedFile] = field(default_factory=list)


@dataclass
class ScanResult:
    processes: list[ScannedProcess] = field(default_factory=list)
    unrecognized: list[dict[str, str]] = field(default_factory=list)  # {path, reason}
    ignored_folders: list[dict[str, str]] = field(default_factory=list)  # {path, reason}
    loose_files: int = 0  # arquivos soltos direto na pasta de um item (não pertencem a um processo)
    duplicate_numbers: list[str] = field(default_factory=list)


def _entries(path: str) -> list[os.DirEntry[str]]:
    with os.scandir(fs_path(path)) as it:
        return sorted(it, key=lambda e: e.name.casefold())


def _relative(project_dir: str, path: str) -> str:
    return os.path.relpath(path, project_dir).replace("\\", "/")


def _infer_status(cancelled: bool, files: list[ScannedFile]) -> str:
    """Estado provável do processo, pelo que existe na pasta. É uma inferência
    — o plano mostra o resultado e quem importa pode corrigir depois."""
    if cancelled:
        return "cancelado"
    types = {f.doc_type for f in files}
    if "nota_fiscal" in types and any("atestad" in fold(f.name) for f in files):
        return "concluido"  # nota fiscal atestada = recebida e conferida
    if "nota_fiscal" in types:
        return "nota_fiscal_emitida"
    # Importação não tem AF: o pedido de importação assinado faz esse papel.
    if "autorizacao_fornecimento" in types or "pedido_importacao" in types:
        return "autorizado"
    return "cotacao"


def _scan_process_folder(project_dir: str, process_path: str) -> list[ScannedFile]:
    files: list[ScannedFile] = []
    for current, dirs, names in os.walk(fs_path(process_path)):
        dirs.sort(key=str.casefold)
        # os.walk devolve o caminho já com o prefixo de caminho longo; tira
        # para montar o caminho relativo certo.
        plain = current[4:] if current.startswith("\\\\?\\") else current
        for name in sorted(names, key=str.casefold):
            if name.startswith("~$") or name.startswith(".") or name.casefold() in _IGNORED_FILES:
                continue
            full = os.path.join(plain, name)
            files.append(
                ScannedFile(
                    rel_path=_relative(project_dir, full),
                    name=name,
                    size_bytes=os.stat(fs_path(full)).st_size,
                    doc_type=classify_document(name),
                )
            )
    return files


def scan_project_folder(project_dir: str) -> ScanResult:
    project_dir = os.path.abspath(project_dir)
    result = ScanResult()
    seen_numbers: set[str] = set()

    for category_entry in _entries(project_dir):
        if not category_entry.is_dir():
            continue
        category_path = os.path.join(project_dir, category_entry.name)
        folded = fold(category_entry.name)
        if folded in PERSONNEL_FOLDERS:
            result.ignored_folders.append(
                {"path": category_entry.name, "reason": "Equipe Executora não usa o fluxo de compra."}
            )
            continue
        category = CATEGORY_FOLDERS.get(folded)
        if category is None:
            result.ignored_folders.append(
                {"path": category_entry.name, "reason": "Pasta que não é uma categoria de despesa."}
            )
            continue

        for item_entry in _entries(category_path):
            item_path = os.path.join(category_path, item_entry.name)
            if not item_entry.is_dir():
                result.loose_files += 1
                continue
            item_match = _ITEM_RE.match(item_entry.name)
            if item_match is None:
                result.unrecognized.append(
                    {"path": _relative(project_dir, item_path), "reason": "Pasta de item fora do padrão 'Item N - descrição'."}
                )
                continue
            item_number = int(item_match.group(1))

            for process_entry in _entries(item_path):
                process_path = os.path.join(item_path, process_entry.name)
                if not process_entry.is_dir():
                    result.loose_files += 1
                    continue
                process_match = _PROCESS_RE.match(process_entry.name)
                if process_match is None:
                    result.unrecognized.append(
                        {
                            "path": _relative(project_dir, process_path),
                            "reason": "Pasta sem nº de processo COPPETEC no nome (esperado AAAA-NNNN).",
                        }
                    )
                    continue

                number = normalize_process_number(f"{process_match.group(1)}-{process_match.group(2)}")
                rest = process_match.group(3)
                cancelled = bool(_CANCELLED_RE.search(rest))
                title = _CANCELLED_RE.sub("", rest).strip(" -–—_.")
                if number in seen_numbers:
                    result.duplicate_numbers.append(number)
                seen_numbers.add(number)

                files = _scan_process_folder(project_dir, process_path)
                result.processes.append(
                    ScannedProcess(
                        category=category,
                        item_number=item_number,
                        item_folder=_relative(project_dir, item_path),
                        folder=_relative(project_dir, process_path),
                        process_number=number,
                        title=title or item_match.group(2).strip() or "(sem título)",
                        cancelled=cancelled,
                        inferred_status=_infer_status(cancelled, files),
                        files=files,
                    )
                )
    return result
