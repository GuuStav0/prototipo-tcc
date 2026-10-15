"""Entrada única das leituras: valida, grava a série, atualiza o último valor e roda o motor
de gatilhos. Usada pela rota POST /ingest/metrics e pelo watchdog (leituras internas).
"""

import threading
from datetime import timedelta

from sqlalchemy.orm import Session

from . import schemas
from .database import as_utc, utcnow
from .domain import METRICS, SOURCES_BY_MODE
from .engine import Reading, TriggerEngine
from .errors import ApiError
from .metrics_store import MetricsStore, StoredSample
from .models import LatestReading, Server

MAX_CLOCK_SKEW = timedelta(seconds=60)

# O SQLite aceita um escritor por vez. Enfileirar as ingestões aqui (em ordem) evita disputa
# pela trava do banco quando muitos coletores enviam ao mesmo tempo; as leituras do dashboard
# continuam em paralelo (modo WAL).
_WRITE_LOCK = threading.Lock()


def _check(sample: schemas.Sample, server: Server | None, source: str, now) -> str | None:
    """Devolve o motivo da rejeição, ou None se a leitura é válida."""
    if server is None:
        return f"servidor '{sample.host_id}' não cadastrado"
    if not server.enabled:
        return f"servidor '{sample.host_id}' está desativado"
    if source != "watchdog":
        # simulado só recebe do simulador; real só de agente/SNMP/IPMI (não se misturam)
        if source not in SOURCES_BY_MODE[server.mode]:
            kind = "simulado" if server.mode == "simulated" else "real"
            return f"servidor '{sample.host_id}' é {kind} e não aceita leituras da fonte '{source}'"
        if server.mode == "real" and not getattr(server, f"{source}_enabled"):
            return f"a coleta por '{source}' está desativada no cadastro de '{sample.host_id}'"
    if as_utc(sample.collected_at) > now + MAX_CLOCK_SKEW:
        return "collected_at está no futuro (verifique o relógio do coletor)"
    if sample.metric == "uptime":
        return None if sample.value >= 0 else "uptime não pode ser negativo"
    spec = METRICS.get(sample.metric)
    if spec is None:
        return f"métrica desconhecida: '{sample.metric}'"
    if not spec["min"] <= sample.value <= spec["max"]:
        return f"valor {sample.value} fora da faixa de {sample.metric} ({spec['min']} a {spec['max']})"
    if sample.metric == "reachable" and sample.value not in (0, 1):
        return "reachable deve ser 0 ou 1"
    return None


def ingest(db: Session, store: MetricsStore, source: str,
           samples: list[schemas.Sample]) -> schemas.IngestResult:
    with _WRITE_LOCK:
        return _ingest(db, store, source, samples)


def _ingest(db: Session, store: MetricsStore, source: str,
            samples: list[schemas.Sample]) -> schemas.IngestResult:
    now = utcnow()
    servers: dict[str, Server | None] = {}
    rejected: list[schemas.Rejected] = []
    accepted: list[schemas.Sample] = []

    for i, sample in enumerate(samples):
        if sample.host_id not in servers:
            servers[sample.host_id] = db.get(Server, sample.host_id)
        reason = _check(sample, servers[sample.host_id], source, now)
        if reason:
            rejected.append(schemas.Rejected(index=i, reason=reason))
        else:
            accepted.append(sample)

    series = [s for s in accepted if s.metric != "uptime"]
    if series:
        try:
            store.write([StoredSample(s.host_id, s.metric, s.value, source, s.collected_at) for s in series], db=db)
        except Exception as exc:
            raise ApiError(503, "metrics_store_unavailable",
                           f"não foi possível gravar as leituras: {exc}") from exc

    # o lote pode ter várias leituras do mesmo host/métrica (ex.: histórico): vale a mais nova
    newest: dict[tuple[str, str], schemas.Sample] = {}
    for s in accepted:
        key = (s.host_id, s.metric)
        if key not in newest or as_utc(s.collected_at) >= as_utc(newest[key].collected_at):
            newest[key] = s

    if source != "watchdog":  # "último contato" do servidor: só leituras enviadas por ele
        for s in accepted:
            if s.metric == "reachable" and s.value == 0:
                continue  # tentativa sem resposta (ex.: SNMP em timeout) não é contato
            server = servers[s.host_id]
            at = as_utc(s.collected_at)
            if server.last_report_at is None or at > server.last_report_at:
                server.last_report_at = at

    for (host_id, metric), s in newest.items():
        if metric == "uptime":
            servers[host_id].uptime_seconds = int(s.value)
            continue
        latest = db.get(LatestReading, (host_id, metric))
        if latest is None:
            db.add(LatestReading(host_id=host_id, metric=metric, value=s.value,
                                 source=source, collected_at=s.collected_at))
        elif as_utc(s.collected_at) >= latest.collected_at:
            latest.value, latest.source, latest.collected_at = s.value, source, s.collected_at

    TriggerEngine(db).process([Reading(s.host_id, s.metric, s.value, s.collected_at) for s in series])
    db.commit()
    return schemas.IngestResult(accepted=len(accepted), rejected=rejected)
