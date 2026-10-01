"""Senha de coordenador do módulo (única, compartilhada por quem administra
qualquer projeto) — hashing PBKDF2 sem dependência nova, e token de sessão
assinado (HMAC + expiração), sem estado no servidor: validar só recalcula a
assinatura, não bate em banco nem em cache.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from app.core.config import settings

_PBKDF2_ITERATIONS = 200_000
_TOKEN_TTL_SECONDS = 12 * 60 * 60  # sessão de coordenador expira sozinha em 12h


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


# Sem MODULE_SECRET_KEY (só possível em DEV_MODE — em produção o módulo nem
# sobe, ver config.check_production_settings): chave aleatória do processo.
# Tokens deixam de valer ao reiniciar, o que em desenvolvimento não importa.
_PROCESS_KEY = os.urandom(32)


def _sign(payload: bytes) -> str:
    key = settings.secret_key.encode("utf-8") if settings.secret_key else _PROCESS_KEY
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def issue_coordenador_token() -> tuple[str, int]:
    expires_at = int(time.time()) + _TOKEN_TTL_SECONDS
    payload = str(expires_at).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii") + "." + _sign(payload)
    return token, expires_at


def verify_coordenador_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload_b64, signature = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
        expires_at = int(payload.decode("utf-8"))
    except Exception:
        return False
    if not hmac.compare_digest(_sign(payload), signature):
        return False
    return time.time() < expires_at
