"""Armazenamento das séries temporais.

Duas implementações com a mesma interface:
- SqliteMetricsStore: padrão, roda sem nada instalado (bom para desenvolvimento e testes);
- InfluxMetricsStore: o banco definido no TCC (4.3), ativado com SMI_METRICS_BACKEND=influx.

Em ambas, os pontos são agregados em janelas alinhadas à época Unix, e o "t" de cada
ponto é o início da janela (mesma convenção do aggregateWindow do InfluxDB).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import Float, Index, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import get_settings
from .database import Base, SessionLocal, as_utc


@dataclass
class StoredSample:
    host_id: str
    metric: str
    value: float
    source: str
    collected_at: datetime


@dataclass
class Stats:
    avg: float | None
    max: float | None
    min: float | None
    count: int


def _epoch(dt: datetime) -> int:
    return int(as_utc(dt).timestamp())


def _bucket_starts(start: datetime, stop: datetime, step: int) -> list[int]:
    first = _epoch(start) // step * step
    last = _epoch(stop)
    return list(range(first, last, step)) or [first]


class MetricsStore:
    def write(self, samples: list[StoredSample]) -> None: ...
    def series(self, host_id: str, metrics: list[str], start: datetime, stop: datetime,
               step: int, aggregation: str) -> dict[str, list[tuple[datetime, float | None]]]: ...
    def stats(self, host_id: str, metric: str, start: datetime, stop: datetime) -> Stats: ...
    def availability(self, start: datetime, stop: datetime, host_ids: list[str] | None = None) -> float | None: ...
    def delete_host(self, host_id: str) -> None: ...
    def health(self) -> str: ...


# ---------------------------------------------------------------- SQLite
class MetricSample(Base):
    __tablename__ = "metric_samples"
    __table_args__ = (Index("ix_samples_host_metric_ts", "host_id", "metric", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[str] = mapped_column(String(63))
    metric: Mapped[str] = mapped_column(String(16))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    ts: Mapped[int] = mapped_column(Integer)  # segundos desde a época, UTC


class SqliteMetricsStore(MetricsStore):
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    def write(self, samples):
        with self._session() as db:
            db.add_all(
                MetricSample(host_id=s.host_id, metric=s.metric, value=s.value,
                             source=s.source, ts=_epoch(s.collected_at))
                for s in samples
            )
            db.commit()

    def series(self, host_id, metrics, start, stop, step, aggregation):
        agg = {"avg": func.avg, "max": func.max, "min": func.min}[aggregation]
        bucket = (MetricSample.ts / step).cast(Integer) * step
        out = {}
        with self._session() as db:
            for metric in metrics:
                rows = db.execute(
                    select(bucket.label("b"), agg(MetricSample.value))
                    .where(MetricSample.host_id == host_id, MetricSample.metric == metric,
                           MetricSample.ts >= _epoch(start), MetricSample.ts < _epoch(stop))
                    .group_by("b")
                ).all()
                values = {b: v for b, v in rows}
                out[metric] = [
                    (datetime.fromtimestamp(b, timezone.utc),
                     round(values[b], 2) if b in values else None)
                    for b in _bucket_starts(start, stop, step)
                ]
        return out

    def stats(self, host_id, metric, start, stop):
        with self._session() as db:
            avg, mx, mn, n = db.execute(
                select(func.avg(MetricSample.value), func.max(MetricSample.value),
                       func.min(MetricSample.value), func.count())
                .where(MetricSample.host_id == host_id, MetricSample.metric == metric,
                       MetricSample.ts >= _epoch(start), MetricSample.ts < _epoch(stop))
            ).one()
        return Stats(avg, mx, mn, n)

    def availability(self, start, stop, host_ids=None):
        q = select(func.avg(MetricSample.value)).where(
            MetricSample.metric == "reachable",
            MetricSample.ts >= _epoch(start), MetricSample.ts < _epoch(stop),
        )
        if host_ids:
            q = q.where(MetricSample.host_id.in_(host_ids))
        with self._session() as db:
            avg = db.execute(q).scalar()
        return None if avg is None else avg * 100

    def delete_host(self, host_id):
        with self._session() as db:
            db.execute(delete(MetricSample).where(MetricSample.host_id == host_id))
            db.commit()

    def health(self):
        return "disabled"  # o campo "influxdb" do /health não se aplica


# ---------------------------------------------------------------- InfluxDB
class InfluxMetricsStore(MetricsStore):
    MEASUREMENT = "hardware"

    def __init__(self, url: str, token: str, org: str, bucket: str):
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        self._client = InfluxDBClient(url=url, token=token, org=org, timeout=10_000)
        self._write = self._client.write_api(write_options=SYNCHRONOUS)
        self._query = self._client.query_api()
        self._org = org
        self._bucket = bucket

    @staticmethod
    def _flux_str(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    @staticmethod
    def _flux_time(dt: datetime) -> str:
        return as_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _base(self, start, stop, predicate: str) -> str:
        return (
            f"from(bucket: {self._flux_str(self._bucket)})"
            f" |> range(start: {self._flux_time(start)}, stop: {self._flux_time(stop)})"
            f' |> filter(fn: (r) => r._measurement == "{self.MEASUREMENT}" and r._field == "value")'
            f" |> filter(fn: (r) => {predicate})"
        )

    def write(self, samples):
        from influxdb_client import Point, WritePrecision

        points = [
            Point(self.MEASUREMENT)
            .tag("host_id", s.host_id).tag("metric", s.metric).tag("source", s.source)
            .field("value", float(s.value))
            .time(as_utc(s.collected_at), WritePrecision.S)
            for s in samples
        ]
        self._write.write(bucket=self._bucket, org=self._org, record=points)

    def series(self, host_id, metrics, start, stop, step, aggregation):
        fn = {"avg": "mean", "max": "max", "min": "min"}[aggregation]
        metric_pred = " or ".join(f"r.metric == {self._flux_str(m)}" for m in metrics)
        flux = (
            self._base(start, stop, f"r.host_id == {self._flux_str(host_id)} and ({metric_pred})")
            + ' |> group(columns: ["metric"])'
            + f' |> aggregateWindow(every: {step}s, fn: {fn}, createEmpty: false, timeSrc: "_start")'
        )
        found: dict[str, dict[int, float]] = {m: {} for m in metrics}
        for table in self._query.query(flux, org=self._org):
            for rec in table.records:
                if rec.get_value() is not None:
                    # a primeira janela vem cortada no início do período (ex. 15:06);
                    # realinha para o início da janela (15:05), como no SQLite
                    bucket = _epoch(rec.get_time()) // step * step
                    found[rec.values["metric"]][bucket] = rec.get_value()
        return {
            m: [
                (datetime.fromtimestamp(b, timezone.utc),
                 round(found[m][b], 2) if b in found[m] else None)
                for b in _bucket_starts(start, stop, step)
            ]
            for m in metrics
        }

    def stats(self, host_id, metric, start, stop):
        base = self._base(
            start, stop,
            f"r.host_id == {self._flux_str(host_id)} and r.metric == {self._flux_str(metric)}",
        ) + " |> group()"
        flux = (
            f"data = {base}\n"
            'data |> mean() |> yield(name: "avg")\n'
            'data |> max() |> yield(name: "max")\n'
            'data |> min() |> yield(name: "min")\n'
            'data |> count() |> yield(name: "count")\n'
        )
        res = {"avg": None, "max": None, "min": None, "count": 0}
        for table in self._query.query(flux, org=self._org):
            for rec in table.records:
                res[rec.values["result"]] = rec.get_value()
        return Stats(res["avg"], res["max"], res["min"], int(res["count"] or 0))

    def availability(self, start, stop, host_ids=None):
        pred = 'r.metric == "reachable"'
        if host_ids:
            pred += " and (" + " or ".join(f"r.host_id == {self._flux_str(h)}" for h in host_ids) + ")"
        flux = self._base(start, stop, pred) + " |> group() |> mean()"
        for table in self._query.query(flux, org=self._org):
            for rec in table.records:
                if rec.get_value() is not None:
                    return rec.get_value() * 100
        return None

    def delete_host(self, host_id):
        self._client.delete_api().delete(
            start=datetime(1970, 1, 1, tzinfo=timezone.utc),
            stop=datetime.now(timezone.utc) + timedelta(days=1),
            predicate=f'_measurement="{self.MEASUREMENT}" AND host_id="{host_id}"',
            bucket=self._bucket, org=self._org,
        )

    def health(self):
        try:
            return "ok" if self._client.ping() else "down"
        except Exception:
            return "down"


@lru_cache
def get_metrics_store() -> MetricsStore:
    s = get_settings()
    if s.metrics_backend == "influx":
        return InfluxMetricsStore(s.influx_url, s.influx_token, s.influx_org, s.influx_bucket)
    if s.metrics_backend == "sqlite":
        return SqliteMetricsStore()
    raise ValueError(f"SMI_METRICS_BACKEND inválido: {s.metrics_backend!r} (use 'sqlite' ou 'influx')")
