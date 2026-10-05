import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# precisa vir antes de importar o app: o banco é criado a partir destas variáveis
_tmp = Path(tempfile.mkdtemp(prefix="smi-test-"))
os.environ["SMI_DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["SMI_METRICS_BACKEND"] = "sqlite"
os.environ["SMI_INGEST_TOKEN"] = "test-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

TOKEN = {"X-Ingest-Token": "test-token"}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def t0():
    """Início de uma sequência de leituras: 10 minutos atrás, alinhado ao segundo."""
    return datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)


def send(client, samples, source="simulator"):
    r = client.post("/api/v1/ingest/metrics", headers=TOKEN, json={
        "source": source,
        "samples": [
            {"host_id": h, "metric": m, "value": v, "collected_at": at.isoformat()}
            for h, m, v, at in samples
        ],
    })
    assert r.status_code == 202, r.text
    return r.json()


def series(client, host, metric, values, start, every=15):
    """Envia uma leitura a cada `every` segundos a partir de `start`."""
    return send(client, [(host, metric, v, start + timedelta(seconds=i * every))
                         for i, v in enumerate(values)])


def alerts(client, **params):
    r = client.get("/api/v1/alerts", params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]
