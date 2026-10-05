"""Geração de relatórios em Markdown a partir dos dados coletados.

Na etapa 4 a IA (via MCP) passa a redigir o texto; até lá, o conteúdo é montado por
modelo fixo com os mesmos números, para a tela de Relatórios já funcionar de verdade.
"""

from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal, utcnow
from .metrics_store import MetricsStore
from .models import Alert, Report, Server, Trigger
from .status import mttr_seconds

TITLES = {
    "availability": "Relatório de Disponibilidade",
    "incidents": "Relatório de Incidentes",
    "performance": "Relatório de Desempenho de Hardware",
    "audit": "Auditoria de Configuração",
}
SEV_PT = {"warning": "Aviso", "critical": "Crítico"}


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def _num(v: float | None, unit: str = "") -> str:
    return "-" if v is None else f"{v:.1f}{unit}".replace(".", ",")


def _alerts_in_period(db: Session, start, stop, host_ids):
    """Alertas que estiveram ativos em algum momento do período."""
    q = select(Alert).where(Alert.started_at < stop,
                            (Alert.resolved_at.is_(None)) | (Alert.resolved_at >= start))
    if host_ids:
        q = q.where(Alert.host_id.in_(host_ids))
    return db.scalars(q.order_by(Alert.started_at)).all()


def build_content(db: Session, store: MetricsStore, report: Report) -> tuple[str, str]:
    start, stop = report.period_from, report.period_to
    host_ids = report.host_ids.split(",") if report.host_ids else None
    servers = db.scalars(select(Server).order_by(Server.id)).all()
    if host_ids:
        servers = [s for s in servers if s.id in host_ids]
    alerts = _alerts_in_period(db, start, stop, host_ids)
    sev = Counter(a.peak_severity for a in alerts)
    availability = store.availability(start, stop, [s.id for s in servers]) if servers else None
    mttr = mttr_seconds(db, start, stop, host_ids)

    lines = [
        f"# {report.title}",
        "",
        f"**Período:** {_fmt_dt(start)} a {_fmt_dt(stop)}  ",
        f"**Escopo:** {', '.join(host_ids) if host_ids else f'toda a infraestrutura ({len(servers)} servidores)'}",
        "",
        "## Resumo",
        "",
        f"- Disponibilidade: **{_num(availability, '%')}**",
        f"- Alertas no período: **{len(alerts)}** "
        f"({sev.get('critical', 0)} crítico(s), {sev.get('warning', 0)} aviso(s))",
        f"- MTTR: **{_fmt_dur(mttr)}**",
        "",
    ]

    if report.type == "availability":
        lines += ["## Disponibilidade por servidor", "", "| Servidor | Disponibilidade |", "| --- | --- |"]
        for s in servers:
            lines.append(f"| {s.id} | {_num(store.availability(start, stop, [s.id]), '%')} |")

    elif report.type == "incidents":
        lines += ["## Alertas", ""]
        if not alerts:
            lines.append("Nenhum alerta no período.")
        else:
            lines += ["| Início | Servidor | Gatilho | Pior severidade | Pior valor | Duração |",
                      "| --- | --- | --- | --- | --- | --- |"]
            for a in alerts:
                end = a.resolved_at or utcnow()
                dur = _fmt_dur((end - a.started_at).total_seconds()) + ("" if a.resolved_at else " (ativo)")
                lines.append(f"| {_fmt_dt(a.started_at)} | {a.host_id} | {a.trigger_name} | "
                             f"{SEV_PT[a.peak_severity]} | {_num(a.value_peak)} | {dur} |")
            by_host = Counter(a.host_id for a in alerts).most_common(3)
            lines += ["", "**Servidores com mais alertas:** "
                      + ", ".join(f"{h} ({n})" for h, n in by_host)]

    elif report.type == "performance":
        lines += ["## Uso de recursos por servidor (média / máximo)", "",
                  "| Servidor | CPU | Memória | Disco | Temperatura |", "| --- | --- | --- | --- | --- |"]
        for s in servers:
            cells = []
            for metric, unit in (("cpu", "%"), ("ram", "%"), ("disk", "%"), ("temp", " °C")):
                st = store.stats(s.id, metric, start, stop)
                cells.append(f"{_num(st.avg, unit)} / {_num(st.max, unit)}")
            lines.append(f"| {s.id} | " + " | ".join(cells) + " |")

    elif report.type == "audit":
        rules = db.scalars(select(Trigger).order_by(Trigger.metric, Trigger.id)).all()
        lines += ["## Regras de gatilho", "",
                  "| Regra | Métrica | Escopo | Aviso | Crítico | Duração | Ativa |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in rules:
            lines.append(f"| {r.name} | {r.metric} ({r.operator}) | {r.host_id or 'global'} | "
                         f"{_num(r.warning_threshold)} | {_num(r.critical_threshold)} | "
                         f"{r.duration_seconds} s | {'sim' if r.enabled else 'não'} |")
        validated = [a for a in alerts if a.validation]
        tp = sum(a.validation == "true_positive" for a in validated)
        precision = f"{tp / len(validated) * 100:.1f}%".replace(".", ",") if validated else "-"
        lines += ["", "## Precisão dos alertas (TCC 4.5)", "",
                  f"- Alertas classificados: {len(validated)} de {len(alerts)}",
                  f"- Precisão (verdadeiros / classificados): **{precision}**"]

    summary = (f"{len(alerts)} alerta(s) no período, disponibilidade {_num(availability, '%')}, "
               f"MTTR {_fmt_dur(mttr)}.")
    return "\n".join(lines) + "\n", summary


def generate_report(report_id: int, store: MetricsStore, session_factory=SessionLocal) -> None:
    """Executada em segundo plano depois de POST /reports."""
    with session_factory() as db:
        report = db.get(Report, report_id)
        if report is None:
            return
        try:
            report.content, report.summary = build_content(db, store, report)
            report.status = "ready"
        except Exception as exc:  # o relatório falha sozinho, sem derrubar a API
            report.status = "failed"
            report.summary = f"Falha ao gerar: {exc}"
        report.completed_at = utcnow()
        db.commit()
