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

A leitura trabalha sobre uma LISTA de entradas (pastas e arquivos com tamanho,
caminhos relativos à pasta do projeto) — a mesma que o `list_tree` do drive
devolve, venha ela do disco deste servidor ou do Horun Agent (ver
`core/drive_backend.py`). `scan_project_folder` é o atalho para uma pasta
local.
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

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


class Entry(Protocol):
    path: str  # relativo à pasta do projeto, posix
    is_dir: bool
    size: int | None


@dataclass
class _Node:
    name: str
    is_dir: bool
    size: int
    children: dict[str, _Node] = field(default_factory=dict)

    def sorted_children(self) -> list[_Node]:
        return sorted(self.children.values(), key=lambda n: n.name.casefold())


def _build_tree(entries: Iterable[Entry]) -> _Node:
    root = _Node(name="", is_dir=True, size=0)
    for entry in entries:
        parts = [p for p in entry.path.split("/") if p]
        node = root
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            child = node.children.get(part)
            if child is None:
                child = _Node(name=part, is_dir=True if not last else entry.is_dir, size=0)
                node.children[part] = child
            if last:
                child.is_dir = entry.is_dir
                child.size = entry.size or 0
            node = child
    return root


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


def _scan_process_folder(node: _Node, rel: str) -> list[ScannedFile]:
    """Arquivos da pasta do processo e das subpastas, na mesma ordem de um
    `os.walk` com nomes em ordem alfabética (arquivos da pasta antes das
    subpastas, sem diferenciar maiúsculas)."""
    files: list[ScannedFile] = []
    children = node.sorted_children()
    for child in children:
        if child.is_dir:
            continue
        name = child.name
        if name.startswith("~$") or name.startswith(".") or name.casefold() in _IGNORED_FILES:
            continue
        files.append(
            ScannedFile(
                rel_path=f"{rel}/{name}",
                name=name,
                size_bytes=child.size,
                doc_type=classify_document(name),
            )
        )
    for child in children:
        if child.is_dir:
            files.extend(_scan_process_folder(child, f"{rel}/{child.name}"))
    return files


def scan_project_folder(project_dir: str) -> ScanResult:
    """Atalho para uma pasta do disco deste servidor (modo local)."""
    project_dir = os.path.abspath(project_dir)
    entries: list[_LocalEntry] = []
    for current, dirs, names in os.walk(fs_path(project_dir)):
        # os.walk devolve o caminho já com o prefixo de caminho longo; tira
        # para montar o caminho relativo certo.
        plain = current[4:] if current.startswith("\\\\?\\") else current
        for name in dirs:
            entries.append(_LocalEntry(_relative(project_dir, os.path.join(plain, name)), True, None))
        for name in names:
            full = os.path.join(plain, name)
            entries.append(_LocalEntry(_relative(project_dir, full), False, os.stat(fs_path(full)).st_size))
    return scan_entries(entries)


@dataclass
class _LocalEntry:
    path: str
    is_dir: bool
    size: int | None


def _relative(project_dir: str, path: str) -> str:
    return os.path.relpath(path, project_dir).replace("\\", "/")


def scan_entries(entries: Iterable[Entry]) -> ScanResult:
    """Lê a estrutura a partir das entradas da pasta do projeto (caminhos
    relativos a ela). Pastas vazias precisam vir como entrada própria — é o
    caso de um processo "(CANCELADO)" sem arquivo nenhum."""
    tree = _build_tree(entries)
    result = ScanResult()
    seen_numbers: set[str] = set()

    for category_node in tree.sorted_children():
        if not category_node.is_dir:
            continue
        folded = fold(category_node.name)
        if folded in PERSONNEL_FOLDERS:
            result.ignored_folders.append(
                {"path": category_node.name, "reason": "Equipe Executora não usa o fluxo de compra."}
            )
            continue
        category = CATEGORY_FOLDERS.get(folded)
        if category is None:
            result.ignored_folders.append(
                {"path": category_node.name, "reason": "Pasta que não é uma categoria de despesa."}
            )
            continue

        for item_node in category_node.sorted_children():
            item_rel = f"{category_node.name}/{item_node.name}"
            if not item_node.is_dir:
                result.loose_files += 1
                continue
            item_match = _ITEM_RE.match(item_node.name)
            if item_match is None:
                result.unrecognized.append(
                    {"path": item_rel, "reason": "Pasta de item fora do padrão 'Item N - descrição'."}
                )
                continue
            item_number = int(item_match.group(1))

            for process_node in item_node.sorted_children():
                process_rel = f"{item_rel}/{process_node.name}"
                if not process_node.is_dir:
                    result.loose_files += 1
                    continue
                process_match = _PROCESS_RE.match(process_node.name)
                if process_match is None:
                    result.unrecognized.append(
                        {
                            "path": process_rel,
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

                files = _scan_process_folder(process_node, process_rel)
                result.processes.append(
                    ScannedProcess(
                        category=category,
                        item_number=item_number,
                        item_folder=item_rel,
                        folder=process_rel,
                        process_number=number,
                        title=title or item_match.group(2).strip() or "(sem título)",
                        cancelled=cancelled,
                        inferred_status=_infer_status(cancelled, files),
                        files=files,
                    )
                )
    return result
