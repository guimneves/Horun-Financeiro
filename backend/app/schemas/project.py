from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    code: str
    name: str
    funding_agency: str = "Petrobras"
    foundation: str = "COPPETEC/UFRJ"
    start_date: date | None = None
    end_date: date | None = None


class ProjectOut(BaseModel):
    id: int
    code: str
    name: str
    funding_agency: str
    foundation: str
    status: str
    start_date: date | None
    end_date: date | None
    active_revision_id: int | None
    drive_folder: str | None = None
    balance_policy: str = "bloquear"
    my_role: str | None = None  # papel do usuário autenticado neste projeto


class ProjectUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    drive_folder: str | None = None  # relativa a MODULE_DRIVE_ROOT; "" remove
    balance_policy: str | None = None  # bloquear | avisar


class MembershipCreate(BaseModel):
    user_id: str
    username: str
    role: str  # coordenador | colaborador


class MembershipOut(BaseModel):
    id: int
    project_id: int
    user_id: str
    username: str
    role: str
    created_at: datetime
