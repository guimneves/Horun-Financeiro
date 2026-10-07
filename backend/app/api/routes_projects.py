from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, update
from sqlmodel import Session, select

from app.core.drive import DriveError, DriveNotFound, project_folder
from app.core.config import settings
from app.core.drive_backend import get_drive_backend
from app.core.identity import HorunIdentity, get_identity
from app.core.files import delete_file
from app.core.permissions import (
    core_role,
    get_membership,
    module_mode,
    require_coordenador,
    require_core_admin,
    require_super_admin,
)
from app.db.models.audit import AuditEvent
from app.db.models.budget import BudgetItem, BudgetPosition, BudgetRevision, ProjectPurchaseCategory
from app.db.models.document import Document
from app.db.models.drive_state import DriveUnlinkedPath
from app.db.models.funding import FundingInstallment
from app.db.models.personnel import Person, PersonnelAssignment
from app.db.models.project import Project, ProjectMembership
from app.db.models.purchase import PurchaseProcess
from app.db.session import get_session
from app.schemas.project import (
    MembershipCreate,
    MembershipOut,
    ProjectCreate,
    ProjectDeleteConfirm,
    ProjectOut,
    ProjectUpdate,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    include_archived: bool = False,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
):
    # Arquivados ficam fora da lista, a menos que se peça (?include_archived=true).
    query = select(Project)
    if not include_archived:
        query = query.where(Project.archived_at.is_(None))  # type: ignore[union-attr]
    if module_mode():
        # Papéis pelo cargo no Horun: todo projeto aparece para quem chegou ao
        # módulo, com o mesmo papel em todos (core/permissions.py).
        role = core_role(identity)
        return [ProjectOut(**p.model_dump(), my_role=role) for p in session.exec(query).all()]
    memberships = session.exec(
        select(ProjectMembership).where(ProjectMembership.user_id == identity.user_id)
    ).all()
    role_by_project = {m.project_id: m.role for m in memberships}
    if not role_by_project:
        return []
    projects = session.exec(
        query.where(Project.id.in_(role_by_project.keys()))  # type: ignore[attr-defined]
    ).all()
    return [
        ProjectOut(**p.model_dump(), my_role=role_by_project.get(p.id))
        for p in projects
    ]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    identity: HorunIdentity = Depends(require_core_admin),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(Project).where(Project.code == body.code)).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um projeto com este código.")

    project = Project(**body.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    # Capturado ANTES do próximo commit: o commit da membership abaixo
    # expira os atributos de `project` na sessão (expire_on_commit padrão
    # do SQLAlchemy), e o model_dump() do SQLModel lê o __dict__ direto —
    # chamado depois disso, viria vazio.
    project_out = ProjectOut(**project.model_dump(), my_role="coordenador")

    # Quem cria o projeto já entra como coordenador — sem isso, no esquema
    # de desenvolvimento ninguém mais conseguiria acessá-lo (get_membership
    # bloquearia até o próprio criador); no modo módulo, é quem passa a
    # receber os avisos do projeto (services/notifications.py).
    membership = ProjectMembership(
        project_id=project.id,
        user_id=identity.user_id,
        username=identity.username,
        role="coordenador",
        granted_by_user_id=identity.user_id,
    )
    session.add(membership)
    session.commit()

    return project_out


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(get_membership),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    return ProjectOut(**project.model_dump(), my_role=membership.role)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(require_coordenador),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("balance_policy") not in (None, "bloquear", "avisar"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Política de saldo inválida (bloquear ou avisar).")
    if "drive_folder" in changes:
        folder = (changes["drive_folder"] or "").strip()
        if folder:
            try:
                folder = project_folder(folder)
                # Existência só no modo local: no modo agente, conferir aqui
                # dependeria do PC do OneDrive estar ligado para salvar a
                # configuração — a tela do drive avisa se a pasta não existir.
                if settings.drive_mode != "agent":
                    get_drive_backend().list_tree(folder, recursive=False)
            except DriveNotFound as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, f"A pasta do projeto não existe no drive: {folder}"
                ) from exc
            except DriveError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        changes["drive_folder"] = folder or None
    for field, value in changes.items():
        setattr(project, field, value)
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectOut(**project.model_dump(), my_role=membership.role)


def _set_archived(session: Session, project_id: int, membership: ProjectMembership, archive: bool) -> ProjectOut:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    if archive and project.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O projeto já está arquivado.")
    if not archive and project.archived_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O projeto não está arquivado.")
    project.archived_at = datetime.now(timezone.utc) if archive else None
    project.archived_by = membership.username if archive else None
    session.add(project)
    record_event(
        session,
        project_id=project_id,
        entity_type="project",
        entity_id=project_id,
        action="projeto_arquivado" if archive else "projeto_desarquivado",
        actor=HorunIdentity(user_id=membership.user_id, username=membership.username, role=""),
    )
    session.commit()
    session.refresh(project)
    return ProjectOut(**project.model_dump(), my_role=membership.role)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(require_coordenador),
):
    """Arquivar: o projeto some da lista e da sincronização automática com o
    drive; nenhum dado é apagado e ele continua abrindo pelo endereço."""
    return _set_archived(session, project_id, membership, archive=True)


@router.post("/{project_id}/unarchive", response_model=ProjectOut)
def unarchive_project(
    project_id: int,
    session: Session = Depends(get_session),
    membership: ProjectMembership = Depends(require_coordenador),
):
    return _set_archived(session, project_id, membership, archive=False)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    body: ProjectDeleteConfirm,
    identity: HorunIdentity = Depends(require_super_admin),
    session: Session = Depends(get_session),
):
    """Exclui o projeto e TODOS os seus dados no Financeiro, numa transação só
    (decisão de 07/10/2026 — só o administrador máximo). Os anexos enviados
    ao servidor são apagados do disco depois do commit; os arquivos do drive
    NUNCA são tocados (documento do tipo "drive" só perde a linha no banco)."""
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    if body.confirm_code.strip() != project.code:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Digite o código do projeto para confirmar.")
    code = project.code

    def ids(model) -> list[int]:
        return list(session.exec(select(model.id).where(model.project_id == project_id)).all())

    purchase_ids = ids(PurchaseProcess)
    assignment_ids = ids(PersonnelAssignment)
    revision_ids = ids(BudgetRevision)
    position_ids = ids(BudgetPosition)

    documents = session.exec(
        select(Document).where(
            Document.purchase_process_id.in_(purchase_ids)  # type: ignore[union-attr]
            | Document.personnel_assignment_id.in_(assignment_ids)  # type: ignore[union-attr]
        )
    ).all()
    upload_paths = [d.storage_path for d in documents if d.storage_kind == "upload"]
    document_ids = [d.id for d in documents]

    # Ordem segura para as chaves estrangeiras (o Postgres confere todas).
    session.exec(delete(Document).where(Document.id.in_(document_ids)))  # type: ignore[call-overload,union-attr]
    session.exec(  # type: ignore[call-overload]
        update(PurchaseProcess).where(PurchaseProcess.project_id == project_id).values(previous_attempt_id=None)
    )
    session.exec(delete(PurchaseProcess).where(PurchaseProcess.project_id == project_id))  # type: ignore[call-overload]
    session.exec(delete(PersonnelAssignment).where(PersonnelAssignment.project_id == project_id))  # type: ignore[call-overload]
    session.exec(delete(Person).where(Person.project_id == project_id))  # type: ignore[call-overload]
    session.exec(  # type: ignore[call-overload]
        delete(BudgetItem).where(
            BudgetItem.revision_id.in_(revision_ids) | BudgetItem.position_id.in_(position_ids)  # type: ignore[attr-defined]
        )
    )
    project.active_revision_id = None
    session.add(project)
    session.flush()
    session.exec(delete(BudgetRevision).where(BudgetRevision.project_id == project_id))  # type: ignore[call-overload]
    session.exec(delete(BudgetPosition).where(BudgetPosition.project_id == project_id))  # type: ignore[call-overload]
    for model in (FundingInstallment, ProjectMembership, DriveUnlinkedPath, AuditEvent, ProjectPurchaseCategory):
        session.exec(delete(model).where(model.project_id == project_id))  # type: ignore[call-overload]
    session.delete(project)
    session.commit()

    # Só depois do commit: se algo acima falhar, nenhum arquivo some.
    for path in upload_paths:
        try:
            delete_file(path)
        except (OSError, ValueError):
            logger.warning("Não foi possível apagar o anexo %s do projeto excluído %s.", path, code)
    # O histórico do projeto foi junto — fica o registro no log do servidor.
    logger.warning(
        "Projeto %s (id %s) EXCLUÍDO por %s (id %s): %d processos de compra, %d documentos (%d anexos apagados).",
        code, project_id, identity.username, identity.user_id, len(purchase_ids), len(document_ids), len(upload_paths),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/members", response_model=list[MembershipOut])
def list_members(
    project_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(get_membership),
):
    members = session.exec(
        select(ProjectMembership).where(ProjectMembership.project_id == project_id)
    ).all()
    return members


@router.post("/{project_id}/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: int,
    body: MembershipCreate,
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    if body.role not in ("coordenador", "colaborador"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Papel inválido.")
    existing = session.exec(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == body.user_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este usuário já tem acesso ao projeto.")

    member = ProjectMembership(
        project_id=project_id,
        user_id=body.user_id,
        username=body.username,
        role=body.role,
        granted_by_user_id=identity.user_id,
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


@router.delete("/{project_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project_id: int,
    membership_id: int,
    session: Session = Depends(get_session),
    _membership: ProjectMembership = Depends(require_coordenador),
):
    member = session.get(ProjectMembership, membership_id)
    if member is None or member.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro não encontrado.")
    if member.role == "coordenador":
        other_coordenadores = session.exec(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.role == "coordenador",
                ProjectMembership.id != membership_id,
            )
        ).first()
        if other_coordenadores is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Não é possível remover o último coordenador do projeto — promova outro membro antes.",
            )
    session.delete(member)
    session.commit()
