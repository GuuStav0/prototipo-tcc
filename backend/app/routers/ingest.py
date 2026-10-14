import secrets

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from .. import schemas
from ..config import get_settings
from ..database import get_db
from ..errors import ApiError
from ..ingestion import ingest
from ..metrics_store import MetricsStore, get_metrics_store

router = APIRouter(prefix="/ingest", tags=["coleta"])


def require_ingest_token(x_ingest_token: str | None = Header(None)) -> None:
    expected = get_settings().ingest_token
    if not x_ingest_token or not secrets.compare_digest(x_ingest_token, expected):
        raise ApiError(401, "invalid_token", "cabeçalho X-Ingest-Token ausente ou inválido")


@router.post("/metrics", response_model=schemas.IngestResult, status_code=202,
             dependencies=[Depends(require_ingest_token)])
def ingest_metrics(batch: schemas.IngestBatch, db: Session = Depends(get_db),
                   store: MetricsStore = Depends(get_metrics_store)):
    return ingest(db, store, batch.source, batch.samples)
