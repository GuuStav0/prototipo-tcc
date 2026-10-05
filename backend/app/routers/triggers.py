from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db, utcnow
from ..domain import MetricKey
from ..engine import reset_rule
from ..errors import ApiError, not_found
from ..models import Server, Trigger

router = APIRouter(prefix="/triggers", tags=["gatilhos"])

# mudar qualquer um destes campos recomeça a avaliação da regra do zero
_RESET_FIELDS = {"metric", "host_id", "operator", "warning_threshold",
                 "critical_threshold", "duration_seconds", "enabled"}


def _get_trigger(db: Session, trigger_id: int) -> Trigger:
    rule = db.get(Trigger, trigger_id)
    if rule is None:
        raise not_found("trigger", trigger_id)
    return rule


def _check_host(db: Session, host_id: str | None) -> None:
    if host_id is not None and db.get(Server, host_id) is None:
        raise ApiError(422, "server_not_found", f"servidor '{host_id}' não existe")


def _reset_overridden_globals(db: Session, rule: Trigger) -> None:
    """Uma regra específica substitui as globais da mesma métrica naquele host."""
    if rule.host_id is None or not rule.enabled:
        return
    globals_ = db.scalars(select(Trigger).where(Trigger.host_id.is_(None), Trigger.metric == rule.metric))
    for g in globals_:
        reset_rule(db, g.id, utcnow(), host_id=rule.host_id)


@router.get("", response_model=schemas.TriggerList)
def list_triggers(host_id: str | None = None, metric: MetricKey | None = None,
                  db: Session = Depends(get_db)):
    q = select(Trigger).order_by(Trigger.id)
    if host_id:
        q = q.where(or_(Trigger.host_id == host_id, Trigger.host_id.is_(None)))
    if metric:
        q = q.where(Trigger.metric == metric)
    return {"items": db.scalars(q).all()}


@router.post("", response_model=schemas.TriggerOut, status_code=201)
def create_trigger(data: schemas.TriggerCreate, db: Session = Depends(get_db)):
    _check_host(db, data.host_id)
    rule = Trigger(**data.model_dump())
    db.add(rule)
    db.flush()
    _reset_overridden_globals(db, rule)
    db.commit()
    return rule


@router.get("/{trigger_id}", response_model=schemas.TriggerOut)
def get_trigger(trigger_id: int, db: Session = Depends(get_db)):
    return _get_trigger(db, trigger_id)


@router.patch("/{trigger_id}", response_model=schemas.TriggerOut)
def update_trigger(trigger_id: int, data: schemas.TriggerUpdate, db: Session = Depends(get_db)):
    rule = _get_trigger(db, trigger_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "metric", "operator", "duration_seconds", "enabled"):
        if field in changes and changes[field] is None:
            raise ApiError(422, "invalid_request", f"{field}: não pode ser null")

    # valida o resultado final (regra atual + alterações), ex.: crítico abaixo do aviso
    current = {f: getattr(rule, f) for f in schemas.TriggerBase.model_fields}
    try:
        schemas.TriggerCreate.model_validate({**current, **changes})
    except ValidationError as exc:
        raise ApiError(422, "invalid_request", exc.errors()[0]["msg"]) from exc
    if "host_id" in changes:
        _check_host(db, changes["host_id"])

    if _RESET_FIELDS & changes.keys():
        reset_rule(db, rule.id, utcnow())
    for field, value in changes.items():
        setattr(rule, field, value)
    db.flush()
    _reset_overridden_globals(db, rule)
    db.commit()
    return rule


@router.delete("/{trigger_id}", status_code=204)
def delete_trigger(trigger_id: int, db: Session = Depends(get_db)):
    rule = _get_trigger(db, trigger_id)
    reset_rule(db, rule.id, utcnow())
    db.delete(rule)
    db.commit()
    return Response(status_code=204)
