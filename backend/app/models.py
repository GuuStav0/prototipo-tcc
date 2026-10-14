from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utcnow


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(120), default="")
    os: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # "simulated" recebe dados só do simulador; "real", só de agente/SNMP/IPMI (etapa 5)
    mode: Mapped[str] = mapped_column(String(10), default="real")

    # Credenciais ficam em texto puro no protótipo; nunca saem pela API.
    snmp_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    snmp_version: Mapped[str] = mapped_column(String(3), default="v2c")
    snmp_port: Mapped[int] = mapped_column(Integer, default=161)
    snmp_community: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snmp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snmp_auth_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snmp_priv_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ipmi_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ipmi_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ipmi_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ipmi_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # última leitura enviada pelo próprio servidor (agente/SNMP/simulador); o watchdog não altera
    last_report_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class LatestReading(Base):
    """Último valor de cada métrica por host (evita consultar a série para o snapshot)."""

    __tablename__ = "latest_readings"

    host_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Trigger(Base):
    __tablename__ = "triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric: Mapped[str] = mapped_column(String(16))
    host_id: Mapped[str | None] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=True
    )
    operator: Mapped[str] = mapped_column(String(3))
    warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class TriggerState(Base):
    """Estado do motor por (gatilho, host): quais níveis estão "travados" e desde quando
    a condição diverge do estado travado (para aplicar a duração ao disparar e ao resolver)."""

    __tablename__ = "trigger_states"

    trigger_id: Mapped[int] = mapped_column(ForeignKey("triggers.id", ondelete="CASCADE"), primary_key=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    warning_latched: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_pending_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    critical_latched: Mapped[bool] = mapped_column(Boolean, default=False)
    critical_pending_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_sample_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_started", "status", "started_at"),
        Index("ix_alerts_host", "host_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Sem chave estrangeira: o histórico sobrevive à remoção da regra ou do servidor.
    trigger_id: Mapped[int] = mapped_column(Integer)
    trigger_name: Mapped[str] = mapped_column(String(120))
    host_id: Mapped[str] = mapped_column(String(63))
    metric: Mapped[str] = mapped_column(String(16))
    unit: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(8))
    peak_severity: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8), default="active")
    threshold: Mapped[float] = mapped_column(Float)
    value_first: Mapped[float] = mapped_column(Float)
    value_peak: Mapped[float] = mapped_column(Float)
    value_last: Mapped[float] = mapped_column(Float)
    first_breach_at: Mapped[datetime] = mapped_column(UTCDateTime)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(16))
    period_from: Mapped[datetime] = mapped_column(UTCDateTime)
    period_to: Mapped[datetime] = mapped_column(UTCDateTime)
    host_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # separados por vírgula
    status: Mapped[str] = mapped_column(String(8), default="pending")
    generated_by: Mapped[str] = mapped_column(String(10), default="system")
    requested_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
