"""Estado dos hosts e indicadores consolidados (Visão Geral)."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .config import get_settings
from .database import utcnow
from .domain import METRICS, SEVERITY_RANK
from .metrics_store import MetricsStore
from .models import Alert, LatestReading, Server

MONITORED = [m for m in METRICS]


def _active_alerts_by_host(db: Session, host_ids: list[str] | None = None) -> dict[str, list[Alert]]:
    q = select(Alert).where(Alert.status == "active")
    if host_ids is not None:
        q = q.where(Alert.host_id.in_(host_ids))
    out: dict[str, list[Alert]] = {}
    for a in db.scalars(q):
        out.setdefault(a.host_id, []).append(a)
    return out


def _worst(alerts: list[Alert]) -> str | None:
    if not alerts:
        return None
    return max((a.severity for a in alerts), key=lambda s: SEVERITY_RANK[s])


def build_servers(db: Session, servers: list[Server], now: datetime | None = None) -> list[schemas.ServerOut]:
    """Monta a visão do contrato: último valor de cada métrica + status derivado.

    Status do host: pior alerta ativo -> senão "ok" se há dados recentes -> senão "unknown".
    """
    now = now or utcnow()
    stale_limit = now - timedelta(seconds=get_settings().stale_after_seconds)
    ids = [s.id for s in servers]

    readings: dict[str, dict[str, LatestReading]] = {}
    for lr in db.scalars(select(LatestReading).where(LatestReading.host_id.in_(ids))):
        readings.setdefault(lr.host_id, {})[lr.metric] = lr
    alerts = _active_alerts_by_host(db, ids)

    result = []
    for s in servers:
        host_readings = readings.get(s.id, {})
        host_alerts = alerts.get(s.id, [])
        # último contato real (as leituras do watchdog não contam: são o backend avisando que o
        # servidor sumiu); bancos antigos sem a coluna preenchida usam o último valor recebido
        last_seen = s.last_report_at or max(
            (r.collected_at for r in host_readings.values() if r.source != "watchdog"), default=None)
        fresh = s.enabled and last_seen is not None and last_seen >= stale_limit

        metrics = {}
        for m in MONITORED:
            lr = host_readings.get(m)
            worst = _worst([a for a in host_alerts if a.metric == m])
            if worst:
                status = worst
            elif lr is not None and lr.collected_at >= stale_limit and s.enabled and lr.source != "watchdog":
                status = "ok"
            else:
                status = "unknown"
            metrics[m] = schemas.MetricReading(
                value=lr.value if lr else None, unit=METRICS[m]["unit"], status=status,
                source=lr.source if lr else None, collected_at=lr.collected_at if lr else None,
            )

        result.append(schemas.ServerOut(
            id=s.id, name=s.name, address=s.address, role=s.role, os=s.os,
            location=s.location, enabled=s.enabled, mode=s.mode,
            collection=schemas.Collection(
                snmp=schemas.SnmpInfo(enabled=s.snmp_enabled, version=s.snmp_version, port=s.snmp_port),
                ipmi=schemas.IpmiInfo(enabled=s.ipmi_enabled, address=s.ipmi_address),
                agent=schemas.AgentInfo(enabled=s.agent_enabled),
            ),
            status=_worst(host_alerts) or ("ok" if fresh else "unknown"),
            last_seen_at=last_seen,
            uptime_seconds=s.uptime_seconds,
            metrics=metrics,
            active_alerts=schemas.AlertCount(
                warning=sum(a.severity == "warning" for a in host_alerts),
                critical=sum(a.severity == "critical" for a in host_alerts),
            ),
            created_at=s.created_at,
        ))
    return result


def mttr_seconds(db: Session, start: datetime, stop: datetime, host_ids: list[str] | None = None) -> int | None:
    """Média de (resolved_at - started_at) dos alertas resolvidos na janela (TCC 2.1)."""
    q = select(Alert.started_at, Alert.resolved_at).where(
        Alert.status == "resolved", Alert.resolved_at >= start, Alert.resolved_at < stop,
    )
    if host_ids:
        q = q.where(Alert.host_id.in_(host_ids))
    durations = [(r - s).total_seconds() for s, r in db.execute(q)]
    return round(sum(durations) / len(durations)) if durations else None


def build_overview(db: Session, store: MetricsStore, range_key: str, seconds: int) -> schemas.Overview:
    now = utcnow()
    start = now - timedelta(seconds=seconds)
    servers = build_servers(db, list(db.scalars(select(Server).order_by(Server.id))), now)

    hosts = schemas.HostCounts(total=len(servers))
    for s in servers:
        setattr(hosts, s.status, getattr(hosts, s.status) + 1)

    active = dict(db.execute(
        select(Alert.severity, func.count()).where(Alert.status == "active").group_by(Alert.severity)
    ).all())
    recent = db.scalars(select(Alert).order_by(Alert.started_at.desc(), Alert.id.desc()).limit(10)).all()

    # só servidores cadastrados (o banco de séries pode ter dados de hosts já removidos)
    availability = store.availability(start, now, [s.id for s in servers]) if servers else None
    return schemas.Overview(
        range=range_key,
        generated_at=now,
        availability=schemas.Availability(
            percent=round(availability, 2) if availability is not None else None,
            slo_percent=get_settings().slo_percent,
        ),
        hosts=hosts,
        alerts_active=schemas.AlertCount(warning=active.get("warning", 0), critical=active.get("critical", 0)),
        mttr_seconds=mttr_seconds(db, start, now),
        recent_alerts=[schemas.AlertOut.model_validate(a) for a in recent],
    )
