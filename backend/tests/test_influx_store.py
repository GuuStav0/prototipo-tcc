"""Confere se o InfluxDB devolve o mesmo que a implementação em SQLite.

Só roda com um InfluxDB disponível:
  SMI_TEST_INFLUX_URL=http://localhost:8086 SMI_TEST_INFLUX_TOKEN=... pytest tests/test_influx_store.py
(org "smi" e bucket "metrics", ou SMI_TEST_INFLUX_ORG / SMI_TEST_INFLUX_BUCKET)
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.database import Base, engine
from app.metrics_store import InfluxMetricsStore, SqliteMetricsStore, StoredSample

URL = os.environ.get("SMI_TEST_INFLUX_URL")
pytestmark = pytest.mark.skipif(not URL, reason="SMI_TEST_INFLUX_URL não definido")


@pytest.fixture
def stores():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    influx = InfluxMetricsStore(
        URL, os.environ["SMI_TEST_INFLUX_TOKEN"],
        os.environ.get("SMI_TEST_INFLUX_ORG", "smi"), os.environ.get("SMI_TEST_INFLUX_BUCKET", "metrics"),
    )
    return SqliteMetricsStore(), influx


def test_influx_matches_sqlite(stores):
    sqlite, influx = stores
    host = f"srv-test-{uuid.uuid4().hex[:8]}"  # host único: o bucket pode ter dados de outras execuções
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(hours=1)
    samples = []
    for i in range(40):  # uma leitura por minuto, com um buraco entre 20 e 24
        if 20 <= i < 25:
            continue
        at = start + timedelta(minutes=i)
        samples += [StoredSample(host, "cpu", 10 + i, "simulator", at),
                    StoredSample(host, "reachable", 0 if i % 10 == 0 else 1, "simulator", at)]
    for store in (sqlite, influx):
        store.write(samples)
    try:
        _compare(sqlite, influx, host, start)
    finally:
        influx.delete_host(host)  # não deixa sobras no bucket mesmo se falhar
    assert all(v is None for _, v in influx.series(host, ["cpu"], start, start + timedelta(hours=1),
                                                   300, "avg")["cpu"])


def _compare(sqlite, influx, host, start):
    stop = start + timedelta(minutes=45)
    for agg in ("avg", "max", "min"):
        a = sqlite.series(host, ["cpu", "reachable"], start, stop, 300, agg)
        b = influx.series(host, ["cpu", "reachable"], start, stop, 300, agg)
        assert a == b, agg

    sa, sb = sqlite.stats(host, "cpu", start, stop), influx.stats(host, "cpu", start, stop)
    assert (sa.max, sa.min, sa.count) == (sb.max, sb.min, sb.count)
    assert sa.avg == pytest.approx(sb.avg)

    assert sqlite.availability(start, stop, [host]) == pytest.approx(influx.availability(start, stop, [host]))
    assert influx.health() == "ok"
