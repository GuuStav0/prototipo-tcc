"""Watchdog ("dead man's switch") para servidores reais.

No modelo de envio (agente), um servidor que cai simplesmente para de mandar dados. Sem este
módulo ele só ficaria "sem dados", sem alerta. Aqui, quando um servidor real fica mais de
heartbeat_timeout_seconds sem enviar nada, o backend registra reachable=0 em nome dele, e a
regra "Host inalcançável" dispara pelo caminho normal do motor de gatilhos.

O silêncio só conta a partir de quando a API subiu: se o PC do monitoramento ficou desligado,
o servidor não tinha para quem enviar, e isso não é falha do servidor.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from . import schemas
from .config import get_settings
from .database import SessionLocal, utcnow
from .ingestion import ingest
from .metrics_store import get_metrics_store
from .models import Server

log = logging.getLogger("smi.watchdog")


def check_once(started_at: datetime, now: datetime | None = None, session_factory=SessionLocal) -> list[str]:
    """Verifica os servidores reais uma vez e devolve os que foram marcados como inalcançáveis."""
    now = now or utcnow()
    timeout = timedelta(seconds=get_settings().heartbeat_timeout_seconds)
    silent = []
    with session_factory() as db:
        servers = db.scalars(select(Server).where(Server.mode == "real", Server.enabled.is_(True))).all()
        for s in servers:
            last = s.last_report_at
            if last is None:
                continue  # recém-cadastrado, nunca enviou nada: fica "sem dados", não é queda
            if now - max(last, started_at) >= timeout:
                silent.append(s.id)
        if silent:
            ingest(db, get_metrics_store(), "watchdog",
                   [schemas.Sample(host_id=h, metric="reachable", value=0, collected_at=now) for h in silent])
    return silent


async def run(stop: asyncio.Event) -> None:
    started_at = utcnow()
    interval = get_settings().poll_interval_seconds
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            pass
        try:
            silent = await asyncio.to_thread(check_once, started_at)
            if silent:
                log.warning("sem dados dos servidores reais: %s (registrado reachable=0)", ", ".join(silent))
        except Exception:  # o watchdog nunca derruba a API
            log.exception("falha na verificação do watchdog")
