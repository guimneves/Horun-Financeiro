"""Registro do histórico de eventos (ver db/models/audit.py). `record_event`
só adiciona à sessão — quem chama faz o commit, junto da mudança que está
sendo registrada, para o evento e a mudança nascerem ou falharem juntos.
"""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from app.core.identity import HorunIdentity
from app.db.models.audit import AuditEvent


def record_event(
    session: Session,
    *,
    project_id: int,
    entity_type: str,
    entity_id: int | None,
    action: str,
    actor: HorunIdentity | None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        detail=json.dumps(detail, ensure_ascii=False, default=str) if detail else "",
        user_id=actor.user_id if actor else "sistema",
        username=actor.username if actor else "sistema",
    )
    session.add(event)
    return event
