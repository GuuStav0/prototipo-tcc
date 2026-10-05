from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import as_utc, get_db, utcnow
from ..domain import METRICS, RANGES_SECONDS, HostStatus
from ..errors import ApiError, not_found
from ..metrics_store import MetricsStore, get_metrics_store
from ..models import Alert, Server
from ..status import build_servers

router = APIRouter(prefix="/servers", tags=["servidores"])


def _get_server(db: Session, host_id: str) -> Server:
    server = db.get(Server, host_id)
    if server is None:
        raise not_found("server", host_id)
    return server


# campos que não aceitam null; os demais (location, credenciais) podem ser apagados com null
_REQUIRED = {"name", "address", "role", "os", "enabled",
             "snmp_enabled", "snmp_version", "snmp_port", "ipmi_enabled", "agent_enabled"}


def _apply(server: Server, data: schemas.ServerUpdate) -> None:
    """Só os campos enviados mudam (PATCH)."""
    values = data.model_dump(exclude_unset=True, exclude={"id"})
    flat = {}
    for group in ("snmp", "ipmi", "agent"):
        for field, value in (values.pop(group, None) or {}).items():
            flat[f"{group}_{field}"] = value
    flat.update(values)
    for column, value in flat.items():
        if value is None and column in _REQUIRED:
            raise ApiError(422, "invalid_request", f"{column}: não pode ser null")
        setattr(server, column, value)


@router.get("", response_model=schemas.ServerList)
def list_servers(status: HostStatus | None = None, db: Session = Depends(get_db)):
    items = build_servers(db, list(db.scalars(select(Server).order_by(Server.id))))
    if status:
        items = [s for s in items if s.status == status]
    return {"items": items}


@router.post("", response_model=schemas.ServerOut, status_code=201)
def create_server(data: schemas.ServerCreate, db: Session = Depends(get_db)):
    if db.get(Server, data.id):
        raise ApiError(409, "server_exists", f"já existe um servidor com id '{data.id}'")
    server = Server(id=data.id, name=data.name, address=data.address, role="", os="")
    _apply(server, data)
    db.add(server)
    db.commit()
    return build_servers(db, [server])[0]


@router.get("/{host_id}", response_model=schemas.ServerOut)
def get_server(host_id: str, db: Session = Depends(get_db)):
    return build_servers(db, [_get_server(db, host_id)])[0]


@router.patch("/{host_id}", response_model=schemas.ServerOut)
def update_server(host_id: str, data: schemas.ServerUpdate, db: Session = Depends(get_db)):
    server = _get_server(db, host_id)
    _apply(server, data)
    db.commit()
    return build_servers(db, [server])[0]


@router.delete("/{host_id}", status_code=204)
def delete_server(host_id: str, db: Session = Depends(get_db),
                  store: MetricsStore = Depends(get_metrics_store)):
    server = _get_server(db, host_id)
    # alertas ficam no histórico, mas não podem continuar "ativos" sem o servidor
    now = utcnow()
    for alert in db.scalars(select(Alert).where(Alert.host_id == host_id, Alert.status == "active")):
        alert.status, alert.resolved_at = "resolved", now
    db.delete(server)
    db.commit()
    store.delete_host(host_id)
    return Response(status_code=204)


# janelas "redondas": evitam buracos periódicos quando a coleta tem intervalo fixo
# (ex.: janela de 288 s com leituras a cada 300 s deixa uma janela vazia a cada 2 h)
NICE_STEPS = [15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400]


def auto_step(span_seconds: int, max_points: int = 300) -> int:
    """Menor janela "redonda" que gera no máximo ~300 pontos."""
    target = span_seconds / max_points
    return next((s for s in NICE_STEPS if s >= target), NICE_STEPS[-1])


def resolve_period(range_: str | None, from_: datetime | None, to: datetime | None,
                   default: str = "24h") -> tuple[datetime, datetime]:
    """from/to têm prioridade sobre range, como diz o contrato."""
    if from_ or to:
        stop = as_utc(to) if to else utcnow()
        start = as_utc(from_) if from_ else stop - timedelta(seconds=RANGES_SECONDS[default])
    else:
        stop = utcnow()
        start = stop - timedelta(seconds=RANGES_SECONDS[range_ or default])
    if start >= stop:
        raise ApiError(422, "invalid_period", "from deve ser anterior a to")
    return start, stop


@router.get("/{host_id}/metrics", response_model=schemas.SeriesList, tags=["métricas"])
def get_metrics(
    host_id: str,
    metric: str = Query(..., description="uma ou mais métricas separadas por vírgula"),
    range: str | None = Query(None, pattern="^(1h|6h|24h|7d|30d)$"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    step: int | None = Query(None, ge=15),
    aggregation: str = Query("avg", pattern="^(avg|max|min)$"),
    db: Session = Depends(get_db),
    store: MetricsStore = Depends(get_metrics_store),
):
    _get_server(db, host_id)
    metrics = [m.strip() for m in metric.split(",") if m.strip()]
    invalid = [m for m in metrics if m not in METRICS]
    if not metrics or invalid:
        raise ApiError(422, "invalid_metric", f"métrica inválida: {', '.join(invalid) or '(vazio)'}")

    start, stop = resolve_period(range, from_, to)
    span = int((stop - start).total_seconds())
    step = step or auto_step(span)
    if span // step > 5000:
        raise ApiError(422, "too_many_points", "step pequeno demais para o período (máx. 5000 pontos)")

    data = store.series(host_id, metrics, start, stop, step, aggregation)
    return {"items": [
        schemas.Series(host_id=host_id, metric=m, unit=METRICS[m]["unit"], from_=start, to=stop,
                       step_seconds=step, aggregation=aggregation,
                       points=[schemas.Point(t=t, v=v) for t, v in data[m]])
        for m in metrics
    ]}
