"""Sincronização das pastas do drive com o banco: transforma o que a leitura
de pastas (`drive_scan`) achou em processos de compra e documentos.

Dois passos separados, de propósito:

- `plan_sync` só calcula o que SERIA feito (nada é gravado) — é o que a rota
  de "ler pastas" devolve para a pessoa conferir;
- `apply_sync` grava, a partir do mesmo plano.

Idempotente: o processo é identificado pelo nº COPPETEC; rodar de novo só
acrescenta os arquivos novos, sem duplicar nem alterar o que já existe. Os
arquivos NÃO são copiados — o documento aponta para o arquivo no drive.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.core.identity import HorunIdentity
from app.db.models.budget import BudgetPosition
from app.db.models.document import Document
from app.db.models.project import Project
from app.db.models.purchase import PurchaseProcess
from app.services.audit import record_event
from app.services.drive_scan import ScannedProcess, ScanResult
from app.services.ledger import LedgerResult

# Estados em que existe nota fiscal: o valor da planilha é o valor final.
_WITH_INVOICE = {"nota_fiscal_emitida", "comprovante_recebimento", "concluido"}
# Estados anteriores à autorização — não conciliam com um valor já lançado na planilha.
_PRE_AUTHORIZATION = {"verificacao_orcamento", "cotacao", "aguardando_autorizacao"}


@dataclass
class ProcessPlan:
    scanned: ScannedProcess
    # criar | criar_da_planilha (só existe na planilha, sem pasta) | existe |
    # sem_item_no_orcamento | duplicado_na_pasta
    action: str
    status: str = ""  # estado com que o processo será criado (vem da pasta, ajustado pela planilha)
    position_id: int | None = None
    existing_process_id: int | None = None
    new_files: int = 0
    value: Decimal = Decimal("0")
    quantity: Decimal = Decimal("1")
    vendor: str | None = None
    value_source: str = "pendente"  # planilha | pendente | cancelado
    warnings: list[str] = field(default_factory=list)


@dataclass
class SyncPlan:
    items: list[ProcessPlan]
    scan: ScanResult
    ledger_skipped: list[str] = field(default_factory=list)
    ledger_unused: list[str] = field(default_factory=list)  # nº de processo da planilha sem pasta correspondente

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "processos_na_pasta": len(self.scan.processes),
            "a_criar": 0,
            "a_criar_so_planilha": 0,
            "ja_existentes": 0,
            "sem_item_no_orcamento": 0,
            "duplicados_na_pasta": 0,
            "arquivos_novos": 0,
            "sem_valor": 0,
            "pastas_nao_reconhecidas": len(self.scan.unrecognized),
            "pastas_ignoradas": len(self.scan.ignored_folders),
            "arquivos_soltos": self.scan.loose_files,
        }
        key = {
            "criar": "a_criar",
            "criar_da_planilha": "a_criar_so_planilha",
            "existe": "ja_existentes",
            "sem_item_no_orcamento": "sem_item_no_orcamento",
            "duplicado_na_pasta": "duplicados_na_pasta",
        }
        for item in self.items:
            counts[key[item.action]] += 1
            counts["arquivos_novos"] += item.new_files
            if item.action == "criar" and item.value_source == "pendente":
                counts["sem_valor"] += 1
        return counts


def plan_sync(session: Session, project: Project, scan: ScanResult, ledger: LedgerResult | None) -> SyncPlan:
    positions = {
        (p.category, p.item_number): p.id
        for p in session.exec(select(BudgetPosition).where(BudgetPosition.project_id == project.id))
    }
    existing = {
        p.process_number: p
        for p in session.exec(select(PurchaseProcess).where(PurchaseProcess.project_id == project.id))
        if p.process_number
    }
    known_paths: dict[int, set[str]] = {}
    if existing:
        for doc in session.exec(
            select(Document).where(
                Document.storage_kind == "drive",
                Document.purchase_process_id.in_([p.id for p in existing.values()]),  # type: ignore[union-attr]
            )
        ):
            known_paths.setdefault(doc.purchase_process_id, set()).add(doc.storage_path)  # type: ignore[arg-type]

    entries = ledger.entries if ledger else {}
    used_ledger: set[str] = set()
    seen: set[str] = set()
    items: list[ProcessPlan] = []

    for scanned in scan.processes:
        plan = ProcessPlan(scanned=scanned, action="criar")
        number = scanned.process_number

        if number in seen:
            plan.action = "duplicado_na_pasta"
            plan.warnings.append("Mesmo nº de processo em mais de uma pasta — só a primeira é usada.")
            items.append(plan)
            continue
        seen.add(number)

        if number in existing:
            process = existing[number]
            plan.action = "existe"
            plan.existing_process_id = process.id
            have = known_paths.get(process.id, set())
            plan.new_files = sum(1 for f in scanned.files if f.rel_path not in have)
            items.append(plan)
            continue

        plan.position_id = positions.get((scanned.category, scanned.item_number))
        if plan.position_id is None:
            plan.action = "sem_item_no_orcamento"
            plan.warnings.append(
                f"O item Nº {scanned.item_number} desta categoria não existe no orçamento do projeto — "
                "cadastre-o na revisão orçamentária e rode de novo."
            )
            items.append(plan)
            continue

        plan.new_files = len(scanned.files)
        plan.status = scanned.inferred_status
        entry = entries.get(number)
        if scanned.cancelled:
            plan.value_source = "cancelado"
            if entry is not None:
                plan.warnings.append("Processo cancelado na pasta, mas com valor na planilha — valor ignorado.")
                used_ledger.add(number)
        elif entry is not None:
            used_ledger.add(number)
            plan.value = entry.value
            plan.quantity = entry.quantity if entry.quantity > 0 else Decimal("1")
            plan.vendor = entry.vendor
            plan.value_source = "planilha"
            if plan.status in _PRE_AUTHORIZATION:
                # Na planilha, ter nº de processo lançado é o que torna o valor
                # "realizado": não faz sentido deixá-lo só como comprometido.
                plan.status = "autorizado"
                plan.warnings.append("Está lançado na planilha, então entra como autorizado (realizado).")
            if entry.category != scanned.category:
                plan.warnings.append(
                    f"A planilha lança este processo em outra categoria ({entry.category}); vale a da pasta."
                )
            if entry.lines > 1:
                plan.warnings.append(f"Valor somado de {entry.lines} linhas da planilha.")
        else:
            plan.warnings.append("Sem valor na planilha — o processo entra com valor zero até alguém preencher.")
        items.append(plan)

    # Lançamentos que só existem na planilha (sem pasta): sem eles, o realizado
    # do programa ficaria abaixo do da planilha. Entram sem arquivos.
    for number in sorted(set(entries) - used_ledger - set(existing) - seen):
        entry = entries[number]
        if entry.item_number is None:
            continue  # sem nº de item não dá para saber onde lançar — fica em `ledger_unused`
        synthetic = ScannedProcess(
            category=entry.category,
            item_number=entry.item_number,
            item_folder="",
            folder="",
            process_number=number,
            title=entry.description or f"Processo {number}",
            cancelled=False,
            inferred_status="autorizado",
        )
        plan = ProcessPlan(
            scanned=synthetic,
            action="criar_da_planilha",
            status="autorizado",
            position_id=positions.get((entry.category, entry.item_number)),
            value=entry.value,
            quantity=entry.quantity if entry.quantity > 0 else Decimal("1"),
            vendor=entry.vendor,
            value_source="planilha",
            warnings=["Só existe na planilha (sem pasta no drive) — entra sem arquivos."],
        )
        if plan.position_id is None:
            plan.action = "sem_item_no_orcamento"
            plan.warnings.append(
                f"O item Nº {entry.item_number} desta categoria não existe no orçamento do projeto."
            )
        else:
            used_ledger.add(number)
        items.append(plan)

    return SyncPlan(
        items=items,
        scan=scan,
        ledger_skipped=ledger.skipped if ledger else [],
        ledger_unused=sorted(set(entries) - used_ledger - set(existing)) if ledger else [],
    )


def apply_sync(session: Session, project: Project, plan: SyncPlan, actor: HorunIdentity) -> dict[str, int]:
    created = 0
    files_added = 0
    now = datetime.now(timezone.utc)

    for item in plan.items:
        scanned = item.scanned
        if item.action in ("criar", "criar_da_planilha"):
            status = item.status
            value = item.value
            unit = (value / item.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            process = PurchaseProcess(
                project_id=project.id,
                budget_position_id=item.position_id,
                process_number=scanned.process_number,
                title=scanned.title,
                vendor=item.vendor,
                quantity=item.quantity,
                estimated_unit_value=unit,
                estimated_value=value,
                final_value=value if status in _WITH_INVOICE else None,
                status=status,
                cancel_reason="Pasta marcada como CANCELADO no drive." if status == "cancelado" else None,
                origin="drive_import",
                drive_rel_path=scanned.folder or None,
                created_by_user_id=actor.user_id,
                created_by_username=actor.username,
                completed_at=now if status == "concluido" else None,
                closed_at=now if status == "cancelado" else None,
            )
            session.add(process)
            session.flush()
            process_id = process.id
            created += 1
            record_event(
                session,
                project_id=project.id,
                entity_type="purchase_process",
                entity_id=process_id,
                action="criado_a_partir_do_drive",
                actor=actor,
                detail={
                    "pasta": scanned.folder or "(só na planilha)",
                    "estado_inferido": status,
                    "valor": value,
                    "fonte_do_valor": item.value_source,
                },
            )
            known: set[str] = set()
        elif item.action == "existe":
            process_id = item.existing_process_id
            known = {
                d.storage_path
                for d in session.exec(
                    select(Document).where(
                        Document.purchase_process_id == process_id, Document.storage_kind == "drive"
                    )
                )
            }
        else:
            continue

        for f in scanned.files:
            if f.rel_path in known:
                continue
            session.add(
                Document(
                    purchase_process_id=process_id,
                    doc_type=f.doc_type,
                    original_filename=f.name,
                    storage_path=f.rel_path,
                    storage_kind="drive",
                    content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                    size_bytes=f.size_bytes,
                    note="Vinculado a partir da pasta do drive.",
                    uploaded_by_user_id=actor.user_id,
                    uploaded_by_username=actor.username,
                )
            )
            files_added += 1

    summary = plan.summary()
    record_event(
        session,
        project_id=project.id,
        entity_type="drive",
        entity_id=None,
        action="sincronizacao_com_o_drive",
        actor=actor,
        detail={"processos_criados": created, "arquivos_vinculados": files_added, "resumo": summary},
    )
    session.commit()
    return {"processos_criados": created, "arquivos_vinculados": files_added}
