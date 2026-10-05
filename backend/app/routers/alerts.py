from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import as_utc, get_db, utcnow
from ..domain import Severity
from ..errors import not_found
from ..models import Alert

router = APIRouter(prefix="/alerts", tags=["alertas"])


@router.get("", response_model=schemas.AlertList)
def list_alerts(
    status: str | None = Query(None, pattern="^(active|resolved)$"),
    severity: Severity | None = None,
    host_id: str | None = None,
    trigger_id: int | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Alert)
    if status:
        q = q.where(Alert.status == status)
    if severity:
        q = q.where(Alert.severity == severity)
    if host_id:
        q = q.where(Alert.host_id == host_id)
    if trigger_id is not None:
        q = q.where(Alert.trigger_id == trigger_id)
    # período: alertas que estiveram ativos em algum momento entre from e to
    if from_:
        q = q.where((Alert.resolved_at.is_(None)) | (Alert.resolved_at >= as_utc(from_)))
    if to:
        q = q.where(Alert.started_at < as_utc(to))

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(q.order_by(Alert.started_at.desc(), Alert.id.desc()).limit(limit).offset(offset)).all()
    return {"items": items, "total": total}


@router.get("/{alert_id}", response_model=schemas.AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise not_found("alert", alert_id)
    return alert


@router.patch("/{alert_id}", response_model=schemas.AlertOut)
def update_alert(alert_id: int, data: schemas.AlertUpdate, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise not_found("alert", alert_id)
    changes = data.model_dump(exclude_unset=True)

    if "acknowledged" in changes:
        if changes["acknowledged"]:
            if alert.acknowledged_at is None:
                alert.acknowledged_at = utcnow()
            alert.acknowledged_by = changes.get("acknowledged_by") or alert.acknowledged_by
        else:
            alert.acknowledged_at = alert.acknowledged_by = None
    elif "acknowledged_by" in changes and alert.acknowledged_at is not None:
        alert.acknowledged_by = changes["acknowledged_by"]
    if "validation" in changes:
        alert.validation = changes["validation"]
    if "note" in changes:
        alert.note = changes["note"]

    db.commit()
    return alert
