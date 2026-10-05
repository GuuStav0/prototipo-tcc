from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import __version__, schemas
from ..database import get_db, utcnow
from ..domain import RANGES_SECONDS
from ..metrics_store import MetricsStore, get_metrics_store
from ..models import LatestReading
from ..status import build_overview

router = APIRouter(tags=["sistema"])


@router.get("/health", response_model=schemas.Health)
def health(db: Session = Depends(get_db), store: MetricsStore = Depends(get_metrics_store)):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
        last_ingest = db.scalar(select(func.max(LatestReading.collected_at)))
    except Exception:
        database, last_ingest = "down", None
    influx = store.health()

    if database == "down":
        status = "down"
    elif influx == "down":
        status = "degraded"
    else:
        status = "ok"
    return schemas.Health(
        status=status, version=__version__, time=utcnow(),
        components=schemas.HealthComponents(database=database, influxdb=influx, last_ingest_at=last_ingest),
    )


@router.get("/overview", response_model=schemas.Overview)
def overview(range: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
             db: Session = Depends(get_db), store: MetricsStore = Depends(get_metrics_store)):
    return build_overview(db, store, range, RANGES_SECONDS[range])
