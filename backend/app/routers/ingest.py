import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from .. import schemas
from ..config import get_settings
from ..database import as_utc, get_db, utcnow
from ..domain import METRICS
from ..engine import Reading, TriggerEngine
from ..errors import ApiError
from ..metrics_store import MetricsStore, StoredSample, get_metrics_store
from ..models import LatestReading, Server

router = APIRouter(prefix="/ingest", tags=["coleta"])

MAX_CLOCK_SKEW = timedelta(seconds=60)


def require_ingest_token(x_ingest_token: str | None = Header(None)) -> None:
    expected = get_settings().ingest_token
    if not x_ingest_token or not secrets.compare_digest(x_ingest_token, expected):
        raise ApiError(401, "invalid_token", "cabeçalho X-Ingest-Token ausente ou inválido")


def _check(sample: schemas.Sample, server: Server | None, now) -> str | None:
    """Devolve o motivo da rejeição, ou None se a leitura é válida."""
    if server is None:
        return f"servidor '{sample.host_id}' não cadastrado"
    if not server.enabled:
        return f"servidor '{sample.host_id}' está desativado"
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


@router.post("/metrics", response_model=schemas.IngestResult, status_code=202,
             dependencies=[Depends(require_ingest_token)])
def ingest_metrics(batch: schemas.IngestBatch, db: Session = Depends(get_db),
                   store: MetricsStore = Depends(get_metrics_store)):
    now = utcnow()
    servers: dict[str, Server | None] = {}
    rejected: list[schemas.Rejected] = []
    accepted: list[schemas.Sample] = []

    for i, sample in enumerate(batch.samples):
        if sample.host_id not in servers:
            servers[sample.host_id] = db.get(Server, sample.host_id)
        reason = _check(sample, servers[sample.host_id], now)
        if reason:
            rejected.append(schemas.Rejected(index=i, reason=reason))
        else:
            accepted.append(sample)

    series = [s for s in accepted if s.metric != "uptime"]
    if series:
        try:
            store.write([StoredSample(s.host_id, s.metric, s.value, batch.source, s.collected_at)
                         for s in series])
        except Exception as exc:
            raise ApiError(503, "metrics_store_unavailable",
                           f"não foi possível gravar as leituras: {exc}") from exc

    # o lote pode ter várias leituras do mesmo host/métrica (ex.: histórico): vale a mais nova
    newest: dict[tuple[str, str], schemas.Sample] = {}
    for s in accepted:
        key = (s.host_id, s.metric)
        if key not in newest or as_utc(s.collected_at) >= as_utc(newest[key].collected_at):
            newest[key] = s

    for (host_id, metric), s in newest.items():
        if metric == "uptime":
            servers[host_id].uptime_seconds = int(s.value)
            continue
        latest = db.get(LatestReading, (host_id, metric))
        if latest is None:
            db.add(LatestReading(host_id=host_id, metric=metric, value=s.value,
                                 source=batch.source, collected_at=s.collected_at))
        elif as_utc(s.collected_at) >= latest.collected_at:
            latest.value, latest.source, latest.collected_at = s.value, batch.source, s.collected_at

    TriggerEngine(db).process([Reading(s.host_id, s.metric, s.value, s.collected_at) for s in series])
    db.commit()
    return schemas.IngestResult(accepted=len(accepted), rejected=rejected)
