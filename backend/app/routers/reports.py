from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import as_utc, get_db, utcnow
from ..domain import RANGES_SECONDS
from ..errors import ApiError, not_found
from ..metrics_store import MetricsStore, get_metrics_store
from ..models import Report, Server
from ..reports import TITLES, generate_report

router = APIRouter(prefix="/reports", tags=["relatórios"])


def _out(report: Report, with_content: bool) -> schemas.ReportOut:
    out = schemas.ReportOut.model_validate({
        **{f: getattr(report, f) for f in schemas.ReportOut.model_fields if f != "host_ids"},
        "host_ids": report.host_ids.split(",") if report.host_ids else None,
    })
    if not with_content:
        out.content = None
    return out


@router.get("", response_model=schemas.ReportList)
def list_reports(db: Session = Depends(get_db)):
    reports = db.scalars(select(Report).order_by(Report.created_at.desc(), Report.id.desc())).all()
    return {"items": [_out(r, with_content=False) for r in reports]}


@router.post("", response_model=schemas.ReportOut, status_code=202)
def create_report(data: schemas.ReportCreate, background: BackgroundTasks,
                  db: Session = Depends(get_db), store: MetricsStore = Depends(get_metrics_store)):
    if data.period_from:
        start, stop = as_utc(data.period_from), as_utc(data.period_to)
    else:
        stop = utcnow()
        start = stop - timedelta(seconds=RANGES_SECONDS[data.range or "7d"])

    if data.host_ids:
        missing = [h for h in data.host_ids if db.get(Server, h) is None]
        if missing:
            raise ApiError(422, "server_not_found", f"servidor(es) inexistente(s): {', '.join(missing)}")

    report = Report(
        title=data.title or TITLES[data.type], type=data.type,
        period_from=start, period_to=stop,
        host_ids=",".join(data.host_ids) if data.host_ids else None,
        status="pending", generated_by="user" if data.requested_by else "system",
        requested_by=data.requested_by,
    )
    db.add(report)
    db.commit()
    background.add_task(generate_report, report.id, store)
    return _out(report, with_content=False)


@router.get("/{report_id}", response_model=schemas.ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise not_found("report", report_id)
    return _out(report, with_content=True)
