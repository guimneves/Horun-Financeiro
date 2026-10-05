"""Avisos (sininho + e-mail) pelo Horun Core — Prompt_Horun_Modulo.md, seção 11.

O módulo não guarda e-mail de ninguém nem fala com SMTP: pede ao Core, que
cria o aviso no sininho de cada destinatário (com link para dentro do módulo)
e manda e-mail a quem tem e-mail cadastrado.

Ligado por duas variáveis de ambiente, lidas a cada chamada:
  HORUN_CORE_URL      ex. http://horun-core-backend:8000
  HORUN_NOTIFY_TOKEN  chave gerada em Core → Admin → Módulos → Notificações
Sem as duas, `notify()` não faz nada (só um registro de debug) — o módulo
funciona igual, só sem avisos. Nunca impede a subida.

A chamada sai em segundo plano (thread), com timeout curto; qualquer erro
(Core fora do ar, chave errada...) só vai para o log — a requisição de quem
usou o módulo nunca falha por causa de um aviso.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from collections.abc import Iterable

logger = logging.getLogger(__name__)

MODULE_ID = "financeiro"
TIMEOUT_SECONDS = 5


def _config() -> tuple[str, str] | None:
    url = (os.environ.get("HORUN_CORE_URL") or "").strip().rstrip("/")
    token = (os.environ.get("HORUN_NOTIFY_TOKEN") or "").strip()
    if not url or not token:
        return None
    return url, token


def _core_ids(user_ids: Iterable[str | int]) -> list[int]:
    """Ids do Core são números (o cabeçalho X-Horun-User-Id); qualquer outro
    valor (ex. "dev" no modo de desenvolvimento) é ignorado."""
    out: list[int] = []
    for raw in user_ids:
        try:
            value = int(str(raw).strip())
        except ValueError:
            continue
        if value not in out:
            out.append(value)
    return out


def _send(url: str, token: str, payload: dict) -> None:
    try:
        request = urllib.request.Request(
            f"{url}/internal/modules/{MODULE_ID}/notify",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (URL do admin)
            logger.debug("Aviso enviado ao Core: %s", response.read(200))
    except Exception:  # noqa: BLE001 — aviso nunca derruba nada
        logger.warning("Não foi possível enviar o aviso %r ao Horun Core.", payload.get("subject"), exc_info=True)


def notify(
    subject: str,
    text: str = "",
    link: str = "",
    user_ids: Iterable[str | int] = (),
    levels: Iterable[int] = (),
    email: bool = True,
) -> threading.Thread | None:
    """Pede ao Core um aviso para `user_ids` (ids do Core) e/ou `levels`
    (1 admin ... 5 IC). `link` é o caminho DENTRO do módulo (ex.
    "/projects/3/purchases/12"). Devolve a thread do envio (os testes usam
    para esperar), ou None quando não há o que enviar."""
    try:
        config = _config()
        if config is None:
            logger.debug("HORUN_CORE_URL/HORUN_NOTIFY_TOKEN ausentes: aviso %r não enviado.", subject)
            return None
        ids = _core_ids(user_ids)
        level_list = [int(lvl) for lvl in levels]
        if not ids and not level_list:
            logger.debug("Aviso %r sem destinatários.", subject)
            return None
        payload = {
            "user_ids": ids,
            "levels": level_list,
            "subject": subject[:150],
            "text": text[:4000],
            "link": link,
            "email": email,
        }
        thread = threading.Thread(target=_send, args=(*config, payload), daemon=True, name="horun-notify")
        thread.start()
        return thread
    except Exception:  # noqa: BLE001
        logger.warning("Falha ao preparar o aviso %r.", subject, exc_info=True)
        return None
