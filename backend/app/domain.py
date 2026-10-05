"""Vocabulário do contrato (docs/contrato/openapi.yaml): métricas, estados e severidades."""

from typing import Literal

MetricKey = Literal["cpu", "ram", "disk", "temp", "reachable"]
Severity = Literal["warning", "critical"]
HostStatus = Literal["ok", "warning", "critical", "unknown"]
Operator = Literal["gt", "gte", "lt", "lte"]
Source = Literal["snmp", "ipmi", "agent", "simulator"]

# unidade e faixa aceita na ingestão (valores fora disso são rejeitados)
METRICS: dict[str, dict] = {
    "cpu": {"unit": "percent", "min": 0, "max": 100},
    "ram": {"unit": "percent", "min": 0, "max": 100},
    "disk": {"unit": "percent", "min": 0, "max": 100},
    "temp": {"unit": "celsius", "min": -40, "max": 150},
    "reachable": {"unit": "bool", "min": 0, "max": 1},
}

SEVERITY_RANK = {"ok": 0, "warning": 1, "critical": 2}

RANGES_SECONDS = {"1h": 3600, "6h": 6 * 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


def compare(operator: str, value: float, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    raise ValueError(f"operador inválido: {operator}")


def is_worse(operator: str, a: float, b: float) -> bool:
    """a é pior que b? Para gt/gte, maior é pior; para lt/lte, menor é pior."""
    return a > b if operator in ("gt", "gte") else a < b
