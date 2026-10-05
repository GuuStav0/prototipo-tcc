"""Motor de gatilhos (TCC 2.4 / 5.2).

Para cada leitura recebida, avalia as regras que valem para aquele host e métrica.
Cada nível (warning e critical) tem um estado "travado" (latched) que só muda depois que a
condição se mantém diferente dele por duration_seconds, tanto para disparar quanto para
resolver. Isso evita alarme por pico isolado e alerta abrindo e fechando (flapping).

Severidade do alerta = o nível mais alto travado. Um aviso que piora vira crítico no MESMO
alerta; quando nenhum nível está travado, o alerta é resolvido.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .database import as_utc
from .domain import METRICS, SEVERITY_RANK, compare, is_worse
from .models import Alert, Trigger, TriggerState

LEVELS = ("warning", "critical")


@dataclass
class Reading:
    host_id: str
    metric: str
    value: float
    collected_at: datetime


class TriggerEngine:
    def __init__(self, db: Session):
        self.db = db
        self._rules_cache: dict[tuple[str, str], list[Trigger]] = {}
        self._states: dict[tuple[int, str], TriggerState] = {}

    # ------------------------------------------------------------ regras
    def rules_for(self, host_id: str, metric: str) -> list[Trigger]:
        """Regras específicas do host substituem as globais da mesma métrica."""
        key = (host_id, metric)
        if key not in self._rules_cache:
            rules = self.db.scalars(
                select(Trigger).where(
                    Trigger.enabled.is_(True),
                    Trigger.metric == metric,
                    or_(Trigger.host_id == host_id, Trigger.host_id.is_(None)),
                ).order_by(Trigger.id)
            ).all()
            specific = [r for r in rules if r.host_id == host_id]
            self._rules_cache[key] = specific or list(rules)
        return self._rules_cache[key]

    def _state(self, trigger_id: int, host_id: str) -> TriggerState:
        # cache local: um estado recém-criado ainda não está no banco, e o lote pode ter
        # várias leituras do mesmo host/métrica
        key = (trigger_id, host_id)
        if key not in self._states:
            state = self.db.get(TriggerState, key)
            if state is None:
                state = TriggerState(trigger_id=trigger_id, host_id=host_id,
                                     warning_latched=False, critical_latched=False)
                self.db.add(state)
            self._states[key] = state
        return self._states[key]

    def _active_alert(self, trigger_id: int, host_id: str) -> Alert | None:
        return self.db.scalars(
            select(Alert).where(Alert.trigger_id == trigger_id, Alert.host_id == host_id,
                                Alert.status == "active")
        ).first()

    # ------------------------------------------------------------ avaliação
    def process(self, readings: list[Reading]) -> None:
        for r in sorted(readings, key=lambda r: as_utc(r.collected_at)):
            for rule in self.rules_for(r.host_id, r.metric):
                self._evaluate(rule, r)
        self.db.flush()

    def _evaluate(self, rule: Trigger, r: Reading) -> None:
        t = as_utc(r.collected_at)
        state = self._state(rule.id, r.host_id)
        if state.last_sample_at is not None and t <= state.last_sample_at:
            return  # leitura repetida ou fora de ordem
        state.last_sample_at = t

        breach_starts: list[datetime] = []
        for level in LEVELS:
            threshold = getattr(rule, f"{level}_threshold")
            latched_attr, pending_attr = f"{level}_latched", f"{level}_pending_since"
            if threshold is None:
                setattr(state, latched_attr, False)
                setattr(state, pending_attr, None)
                continue

            meets = compare(rule.operator, r.value, threshold)
            if meets == getattr(state, latched_attr):
                setattr(state, pending_attr, None)
                continue

            pending = getattr(state, pending_attr) or t
            setattr(state, pending_attr, pending)
            if (t - pending).total_seconds() >= rule.duration_seconds:
                setattr(state, latched_attr, meets)
                setattr(state, pending_attr, None)
                if meets:
                    breach_starts.append(pending)

        severity = ("critical" if state.critical_latched
                    else "warning" if state.warning_latched else None)
        alert = self._active_alert(rule.id, r.host_id)

        if severity and alert is None:
            self.db.add(Alert(
                trigger_id=rule.id, trigger_name=rule.name, host_id=r.host_id,
                metric=r.metric, unit=METRICS[r.metric]["unit"],
                severity=severity, peak_severity=severity, status="active",
                threshold=getattr(rule, f"{severity}_threshold"),
                value_first=r.value, value_peak=r.value, value_last=r.value,
                first_breach_at=min(breach_starts) if breach_starts else t,
                started_at=t,
            ))
        elif severity and alert is not None:
            alert.severity = severity
            alert.threshold = getattr(rule, f"{severity}_threshold")
            if SEVERITY_RANK[severity] > SEVERITY_RANK[alert.peak_severity]:
                alert.peak_severity = severity
            if is_worse(rule.operator, r.value, alert.value_peak):
                alert.value_peak = r.value
            alert.value_last = r.value
        elif alert is not None:
            alert.status = "resolved"
            alert.resolved_at = t
            alert.value_last = r.value

        if severity or alert is not None:
            # a próxima leitura do mesmo lote precisa enxergar o alerta aberto/fechado
            self.db.flush()


def reset_rule(db: Session, trigger_id: int, at: datetime, host_id: str | None = None) -> None:
    """Resolve os alertas ativos de uma regra e zera seu estado (regra desativada,
    removida, alterada ou substituída por uma regra específica do host)."""
    alerts = select(Alert).where(Alert.trigger_id == trigger_id, Alert.status == "active")
    states = select(TriggerState).where(TriggerState.trigger_id == trigger_id)
    if host_id is not None:
        alerts = alerts.where(Alert.host_id == host_id)
        states = states.where(TriggerState.host_id == host_id)
    for alert in db.scalars(alerts):
        alert.status = "resolved"
        alert.resolved_at = at
    for state in db.scalars(states):
        db.delete(state)
