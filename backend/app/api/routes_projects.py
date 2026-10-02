from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.drive import DriveError, DriveNotFound, project_folder
from app.core.config import settings
from app.core.drive_backend import get_drive_backend
from app.core.identity import HorunIdentity, get_identity
from app.core.permissions import get_membership, require_coordenador, require_core_admin
from app.db.models.project import Project, ProjectMembership
from app.db.session import get_session
from app.schemas.project import (
    MembershipCreate,
    MembershipOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    identity: HorunIdentity = Depends(get_identity),
    session: Session = Depends(get_session),
):
    memberships = session.exec(
        select(ProjectMembership).where(ProjectMembership.user_id == identity.user_id)
    ).all()
    role_by_project = {m.project_id: m.role for m in memberships}
    if not role_by_project:
        return []
    projects = session.exec(
        select(Project).where(Project.id.in_(role_by_project.keys()))  # type: ignore[attr-defined]
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

    # Quem cria o projeto já entra como coordenador — sem isso, ninguém
    # mais conseguiria acessá-lo (get_membership bloquearia até o próprio
    # criador).
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
