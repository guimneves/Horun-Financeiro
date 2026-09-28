from __future__ import annotations

from pydantic import BaseModel


class KnownUserOut(BaseModel):
    user_id: str
    username: str
