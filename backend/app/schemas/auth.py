from __future__ import annotations

from pydantic import BaseModel


class CoordenadorLoginRequest(BaseModel):
    password: str


class CoordenadorLoginResponse(BaseModel):
    token: str
    expires_at: int


class CoordenadorPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
