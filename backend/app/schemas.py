"""Formatos de entrada e saída da API, espelhando docs/contrato/openapi.yaml."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import HostStatus, MetricKey, Operator, Severity, Source


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- servidores ----------
class MetricReading(BaseModel):
    value: float | None = None
    unit: str
    status: HostStatus = "unknown"
    source: Source | None = None
    collected_at: datetime | None = None


class SnmpInfo(BaseModel):
    enabled: bool
    version: Literal["v2c", "v3"]
    port: int


class IpmiInfo(BaseModel):
    enabled: bool
    address: str | None = None


class AgentInfo(BaseModel):
    enabled: bool


class Collection(BaseModel):
    snmp: SnmpInfo
    ipmi: IpmiInfo
    agent: AgentInfo


class AlertCount(BaseModel):
    warning: int = 0
    critical: int = 0


class ServerOut(BaseModel):
    id: str
    name: str
    address: str
    role: str
    os: str
    location: str | None
    enabled: bool
    collection: Collection
    status: HostStatus
    last_seen_at: datetime | None
    uptime_seconds: int | None
    metrics: dict[str, MetricReading]
    active_alerts: AlertCount
    created_at: datetime


class SnmpInput(BaseModel):
    enabled: bool | None = None
    version: Literal["v2c", "v3"] | None = None
    port: int | None = Field(None, ge=1, le=65535)
    community: str | None = None
    username: str | None = None
    auth_password: str | None = None
    priv_password: str | None = None


class IpmiInput(BaseModel):
    enabled: bool | None = None
    address: str | None = None
    username: str | None = None
    password: str | None = None


class AgentInput(BaseModel):
    enabled: bool | None = None


class ServerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    address: str | None = Field(None, min_length=1)
    role: str | None = None
    os: str | None = None
    location: str | None = None
    enabled: bool | None = None
    snmp: SnmpInput | None = None
    ipmi: IpmiInput | None = None
    agent: AgentInput | None = None


class ServerCreate(ServerUpdate):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str = Field(min_length=1)
    address: str = Field(min_length=1)


class ServerList(BaseModel):
    items: list[ServerOut]


# ---------- métricas ----------
class Point(BaseModel):
    t: datetime
    v: float | None


class Series(BaseModel):
    host_id: str
    metric: MetricKey
    unit: str
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    step_seconds: int
    aggregation: Literal["avg", "max", "min"]
    points: list[Point]


class SeriesList(BaseModel):
    items: list[Series]


# ---------- gatilhos ----------
class TriggerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    metric: MetricKey
    host_id: str | None = None
    operator: Operator
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    duration_seconds: int = Field(60, ge=0)
    enabled: bool = True


def _check_thresholds(operator, warning, critical):
    if warning is None and critical is None:
        raise ValueError("informe ao menos um limiar (warning_threshold ou critical_threshold)")
    if warning is not None and critical is not None:
        # o crítico precisa ser "mais grave" que o aviso, senão um nível nunca acontece
        if operator in ("gt", "gte") and critical < warning:
            raise ValueError("para gt/gte, critical_threshold deve ser >= warning_threshold")
        if operator in ("lt", "lte") and critical > warning:
            raise ValueError("para lt/lte, critical_threshold deve ser <= warning_threshold")


class TriggerCreate(TriggerBase):
    @model_validator(mode="after")
    def _thresholds(self):
        _check_thresholds(self.operator, self.warning_threshold, self.critical_threshold)
        return self


class TriggerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    metric: MetricKey | None = None
    host_id: str | None = None
    operator: Operator | None = None
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    duration_seconds: int | None = Field(None, ge=0)
    enabled: bool | None = None


class TriggerOut(TriggerBase, ORM):
    id: int
    created_at: datetime
    updated_at: datetime


class TriggerList(BaseModel):
    items: list[TriggerOut]


# ---------- alertas ----------
Validation = Literal["true_positive", "false_positive"]


class AlertOut(ORM):
    id: int
    trigger_id: int
    trigger_name: str
    host_id: str
    metric: MetricKey
    unit: str
    severity: Severity
    peak_severity: Severity
    status: Literal["active", "resolved"]
    threshold: float
    value_first: float
    value_peak: float
    value_last: float
    first_breach_at: datetime
    started_at: datetime
    resolved_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    validation: Validation | None
    note: str | None


class AlertList(BaseModel):
    items: list[AlertOut]
    total: int


class AlertUpdate(BaseModel):
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    validation: Validation | None = None
    note: str | None = None


# ---------- visão geral ----------
class Availability(BaseModel):
    percent: float | None
    slo_percent: float


class HostCounts(BaseModel):
    total: int = 0
    ok: int = 0
    warning: int = 0
    critical: int = 0
    unknown: int = 0


class Overview(BaseModel):
    range: str
    generated_at: datetime
    availability: Availability
    hosts: HostCounts
    alerts_active: AlertCount
    mttr_seconds: int | None
    recent_alerts: list[AlertOut]


# ---------- relatórios ----------
ReportType = Literal["availability", "incidents", "performance", "audit"]


class ReportOut(ORM):
    id: int
    title: str
    type: ReportType
    period_from: datetime
    period_to: datetime
    host_ids: list[str] | None
    status: Literal["pending", "ready", "failed"]
    generated_by: Literal["system", "user", "assistant"]
    requested_by: str | None
    created_at: datetime
    completed_at: datetime | None
    summary: str | None
    content: str | None = None


class ReportList(BaseModel):
    items: list[ReportOut]


class ReportCreate(BaseModel):
    type: ReportType
    title: str | None = None
    range: Literal["24h", "7d", "30d"] | None = None
    period_from: datetime | None = None
    period_to: datetime | None = None
    host_ids: list[str] | None = None
    requested_by: str | None = None

    @model_validator(mode="after")
    def _period(self):
        if (self.period_from is None) != (self.period_to is None):
            raise ValueError("informe period_from e period_to juntos")
        if self.period_from and self.period_from >= self.period_to:
            raise ValueError("period_from deve ser anterior a period_to")
        return self


# ---------- coleta ----------
class Sample(BaseModel):
    host_id: str
    # "uptime" (segundos) só atualiza o servidor; não vira série nem gatilho
    metric: str
    value: float
    collected_at: datetime


class IngestBatch(BaseModel):
    source: Source
    collector_id: str | None = None
    samples: list[Sample] = Field(max_length=5000)


class Rejected(BaseModel):
    index: int
    reason: str


class IngestResult(BaseModel):
    accepted: int
    rejected: list[Rejected]


# ---------- assistente ----------
class ChatRequest(BaseModel):
    conversation_id: str | None = Field(None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class ToolCallOut(BaseModel):
    name: str
    arguments: dict


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolCallOut]
    created_at: datetime


class McpStatus(BaseModel):
    connected: bool
    tools: list[str]
    detail: str


class AssistantStatus(BaseModel):
    enabled: bool
    provider: str | None
    model: str | None
    available: bool
    detail: str
    mcp: McpStatus


# ---------- sistema ----------
class HealthComponents(BaseModel):
    database: Literal["ok", "down"]
    influxdb: Literal["ok", "down", "disabled"]
    last_ingest_at: datetime | None


class Health(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str
    time: datetime
    components: HealthComponents
