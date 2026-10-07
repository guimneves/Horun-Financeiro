"""Sincronização automática com o drive, nos dois sentidos (decisão do
mantenedor, 06/10/2026): a cada `MODULE_DRIVE_AUTO_SYNC_MINUTES` minutos
(padrão 30; 0 = desligada; desligada também sem drive configurado):

1. para cada projeto com pasta do drive, faz o mesmo que o botão
   "Sincronizar" (plano + aplicação), com a identidade "sincronização
   automática": pastas, arquivos e valores novos aparecem sem ninguém clicar;
2. lê o nº das autorizações de fornecimento dos processos sem nº
   (services/af_number.py);
3. tenta de novo o que ficou pendente na escrita (pastas "SEM NUMERO" a
   renomear, cópias de anexos) — services/drive_write.py.

Mesmo padrão do RE7S (app/modules/auto_sync.py): o que decide "se roda" fica
no banco (`DriveAutoSyncState`, uma linha) — `last_run_at` (a próxima rodada
só depois do intervalo; reiniciar não adianta nem atrasa) e `lease_until`
(concessão por UPDATE condicional: com vários workers, só um roda). Com o
agente sem sinal a rodada é pulada em silêncio e conferida de novo no
próximo ciclo. O laço nunca morre por erro.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import drive_configured, settings
from app.core.identity import HorunIdentity
from app.db.models.drive_state import DriveAutoSyncState
from app.db.models.project import Project
from app.services.drive_sync import apply_sync, sync_lock

logger = logging.getLogger("financeiro.drive_auto_sync")

STATE_ID = 1
LEASE_SECONDS = 15 * 60  # tempo máximo que uma rodada segura a vez
ERROR_RETRY_SECONDS = 10 * 60  # depois de um erro geral, tenta de novo antes do intervalo inteiro

SYSTEM_ACTOR = HorunIdentity(user_id="sistema", username="sincronização automática", role="system")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def enabled() -> bool:
    return settings.drive_auto_sync_minutes > 0 and drive_configured()


def interval() -> timedelta:
    return timedelta(minutes=max(settings.drive_auto_sync_minutes, 1))


def get_state(session: Session) -> DriveAutoSyncState:
    state = session.get(DriveAutoSyncState, STATE_ID)
    if state is not None:
        return state
    try:
        session.add(DriveAutoSyncState(id=STATE_ID))
        session.commit()
    except IntegrityError:  # outro worker criou ao mesmo tempo
        session.rollback()
    return session.get(DriveAutoSyncState, STATE_ID)  # type: ignore[return-value]


def _acquire_lease(session: Session, now: datetime, *, force: bool) -> bool:
    conditions = [
        DriveAutoSyncState.id == STATE_ID,
        or_(DriveAutoSyncState.lease_until.is_(None), DriveAutoSyncState.lease_until < now),  # type: ignore[union-attr]
    ]
    if not force:
        conditions.append(
            or_(DriveAutoSyncState.last_run_at.is_(None), DriveAutoSyncState.last_run_at <= now - interval())  # type: ignore[union-attr,operator]
        )
    result = session.execute(
        update(DriveAutoSyncState)
        .where(*conditions)
        .values(lease_until=now + timedelta(seconds=LEASE_SECONDS))
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return result.rowcount == 1


def _finish(session: Session, *, status: str, message: str, detail: dict | None = None,
            success: bool = False, retry_at: datetime | None = None) -> None:
    session.expire_all()
    state = get_state(session)
    state.last_status = status
    state.last_message = message
    if detail is not None:
        state.last_detail = json.dumps(detail, ensure_ascii=False)
    if success:
        state.last_run_at = _now()
    state.lease_until = retry_at
    session.add(state)
    session.commit()


def _agent_offline() -> bool:
    if settings.drive_mode != "agent":
        return False
    from app.services.agent_bridge import agent_state

    state = agent_state()
    return not (state.online and state.extended)


def sync_projects(session: Session) -> dict[int, dict]:
    """Passo 2: plano + aplicação em cada projeto com pasta do drive. Um
    projeto com problema (pasta sumiu, planilha aberta no Excel) não impede
    os outros. Só grava (e registra no histórico) quando há algo novo."""
    from app.api.routes_drive import PlanError, build_sync_plan

    detail: dict[int, dict] = {}
    # Projetos arquivados ficam de fora (decisão de 07/10/2026).
    projects = session.exec(
        select(Project).where(
            Project.drive_folder.is_not(None),  # type: ignore[union-attr]
            Project.archived_at.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    for project in projects:
        if not (project.drive_folder or "").strip():
            continue
        try:
            plan = build_sync_plan(session, project, None)
            summary = plan.summary()
            to_create = (
                summary["a_criar"] + summary["a_criar_so_planilha"] + summary["a_criar_sem_numero"]
                + summary["valores_a_preencher"] + summary["itens_a_corrigir"]
            )
            if to_create == 0 and summary["arquivos_novos"] == 0:
                detail[project.id] = {"arquivos": 0, "processos": 0}
                continue
            result = apply_sync(session, project, plan, SYSTEM_ACTOR)
            detail[project.id] = {
                "arquivos": result["arquivos_vinculados"],
                "processos": result["processos_criados"],
            }
        except PlanError as exc:
            session.rollback()
            detail[project.id] = {"arquivos": 0, "processos": 0, "erro": str(exc)}
        except Exception as exc:  # noqa: BLE001 — um projeto não derruba a rodada
            session.rollback()
            logger.exception("Sincronização automática falhou no projeto %s", project.id)
            detail[project.id] = {"arquivos": 0, "processos": 0, "erro": f"Erro inesperado: {exc}"}
    return detail


def run_once(session: Session) -> dict:
    """Uma passagem completa (sem concessão nem trava — quem chama cuida).
    Devolve o detalhe por projeto e o que foi refeito na escrita."""
    from app.services.af_number import retry_missing_numbers
    from app.services.drive_write import retry_pending

    # pastas/arquivos novos primeiro; depois o nº das AFs (inclusive as que
    # acabaram de ser vinculadas); por fim a escrita pendente — já com as
    # pastas "SEM NUMERO" que ganharam nº agora
    projects = sync_projects(session)
    numbers = retry_missing_numbers(session)
    pending = retry_pending(session)
    return {"escrita": pending, "numeros_lidos": numbers, "projetos": projects}


def run_auto_sync(bind, *, force: bool = False) -> str:
    """Uma rodada: "disabled" | "not_due" | "busy" | "skipped" | "ok" |
    "partial" | "error". `force` ignora o intervalo (nunca a concessão)."""
    with Session(bind) as session:
        if not enabled():
            return "disabled"
        get_state(session)
        if not _acquire_lease(session, _now(), force=force):
            return "not_due"
        if not sync_lock.acquire(blocking=False):
            # sincronização pelo botão em andamento: só devolve a vez
            _finish(session, status="pulada", message="Sincronização manual em andamento.")
            return "busy"
        try:
            if _agent_offline():
                _finish(session, status="pulada", message="Horun Agent sem sinal — tento de novo mais tarde.")
                return "skipped"
            try:
                result = run_once(session)
            except Exception as exc:  # noqa: BLE001 — o laço nunca pode morrer
                session.rollback()
                logger.exception("Sincronização automática falhou")
                _finish(session, status="erro", message=f"Erro inesperado: {exc}",
                        retry_at=_now() + timedelta(seconds=ERROR_RETRY_SECONDS))
                return "error"
            projects = result["projetos"]
            files = sum(p.get("arquivos", 0) for p in projects.values())
            created = sum(p.get("processos", 0) for p in projects.values())
            copies = result["escrita"]["copias"]
            errors = [p for p in projects.values() if p.get("erro")]
            message = f"{files} arquivo(s) novo(s), {created} processo(s) novo(s), {copies} cópia(s) gravada(s) no drive."
            status = "parcial" if errors else "ok"
            _finish(session, status=status, message=message,
                    detail={"projetos": {str(k): v for k, v in projects.items()}, **{
                        "escrita": result["escrita"], "numeros_lidos": result["numeros_lidos"]}},
                    success=True)
            return "partial" if errors else "ok"
        finally:
            sync_lock.release()


def project_info(session: Session, project_id: int) -> dict:
    """O que a tela do drive mostra sobre a sincronização automática."""
    info: dict = {"enabled": enabled(), "interval_minutes": settings.drive_auto_sync_minutes}
    state = session.get(DriveAutoSyncState, STATE_ID)
    if state is None:
        return info
    info.update(last_run_at=_as_utc(state.last_run_at), last_status=state.last_status, last_message=state.last_message)
    try:
        detail = json.loads(state.last_detail or "{}")
    except ValueError:
        detail = {}
    mine = (detail.get("projetos") or {}).get(str(project_id)) or {}
    info.update(new_files=mine.get("arquivos", 0), new_processes=mine.get("processos", 0), error=mine.get("erro"))
    info["copies"] = (detail.get("escrita") or {}).get("copias", 0)
    return info


def tick(bind) -> None:
    try:
        run_auto_sync(bind)
    except Exception:  # noqa: BLE001
        logger.exception("Falha na sincronização automática com o drive")


async def loop(bind) -> None:
    """Iniciado no `lifespan` (main.py). Confere o banco a cada
    `drive_auto_sync_check_seconds`; a sincronização roda numa thread."""
    await asyncio.sleep(min(60.0, settings.drive_auto_sync_check_seconds))
    while True:
        await asyncio.to_thread(tick, bind)
        await asyncio.sleep(settings.drive_auto_sync_check_seconds)
