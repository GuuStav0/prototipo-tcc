import { Link } from "react-router-dom";
import { Gauge, Server, AlertTriangle, Clock, ChevronRight } from "lucide-react";
import { api } from "../../api/client";
import { LIVE_INTERVAL, SERIES_INTERVAL, useApi } from "../../hooks/useApi";
import { useLive } from "../../context/live";
import { STATUS, STATUS_ORDER } from "../../config/status";
import { METRIC_META } from "../../config/metrics";
import { formatDuration, formatPercent, formatRelative } from "../../utils/format";
import KpiCard from "../../components/KpiCard/KpiCard";
import Led from "../../components/Led/Led";
import MiniChart from "../../components/charts/MiniChart";
import { ErrorBox, Loading, Empty } from "../../components/Feedback/Feedback";

export default function Dashboard() {
  const { overview, error, reload } = useLive();
  const servers = useApi((signal) => api.servers(undefined, { signal }), ["servers"], { interval: LIVE_INTERVAL });

  if (!overview) return error ? <ErrorBox error={error} onRetry={reload} /> : <Loading />;

  const { hosts, alerts_active: active, availability } = overview;
  const totalActive = active.warning + active.critical;
  const sloMet = availability.percent === null || availability.percent >= availability.slo_percent;

  return (
    <div className="smi-stack">
      <div className="smi-grid-kpi">
        <KpiCard
          icon={Gauge}
          label="Disponibilidade (24 h)"
          value={formatPercent(availability.percent)}
          sub={`meta SRE: ${formatPercent(availability.slo_percent)}`}
          tone={sloMet ? STATUS.ok.color : STATUS.critical.color}
        />
        <KpiCard
          icon={Server}
          label="Hosts saudáveis"
          value={`${hosts.ok}/${hosts.total}`}
          sub={hosts.unknown ? `${hosts.unknown} sem dados recentes` : "todos com coleta em dia"}
          tone="#7DD3FC"
        />
        <KpiCard
          icon={AlertTriangle}
          label="Alertas ativos"
          value={totalActive}
          sub={`${active.critical} crítico · ${active.warning} aviso`}
          tone={totalActive ? STATUS.critical.color : STATUS.ok.color}
        />
        <KpiCard icon={Clock} label="MTTR médio" value={formatDuration(overview.mttr_seconds)} sub="alertas resolvidos em 24 h" tone="#A78BFA" />
      </div>

      <div className="smi-grid-2">
        <div className="smi-card">
          <div className="smi-card-title">Estado dos servidores</div>
          <div className="smi-severity-bar">
            {STATUS_ORDER.map((s) =>
              hosts[s] ? <div key={s} style={{ width: `${(hosts[s] / hosts.total) * 100}%`, background: STATUS[s].color }} /> : null,
            )}
          </div>
          <div className="smi-legend">
            {STATUS_ORDER.map((s) => (
              <span key={s}><Led status={s} /> {STATUS[s].label} · {hosts[s]}</span>
            ))}
          </div>
        </div>

        <div className="smi-card">
          <div className="smi-card-title-row">
            <div className="smi-card-title" style={{ margin: 0 }}>Últimos disparos</div>
            <Link className="smi-link" to="/gatilhos">Ver todos <ChevronRight size={14} /></Link>
          </div>
          {overview.recent_alerts.length === 0 ? (
            <Empty>Nenhum alerta registrado.</Empty>
          ) : (
            <div className="smi-alertlist">
              {overview.recent_alerts.slice(0, 5).map((a) => (
                <div className="smi-alertrow" key={a.id}>
                  <Led status={a.status === "active" ? a.severity : "ok"} pulse />
                  <div className="smi-alertrow-body">
                    <span className="smi-alertrow-name">{a.trigger_name}</span>
                    <span className="smi-muted smi-mono">
                      {a.host_id} · {a.status === "active" ? STATUS[a.severity].label : "resolvido"}
                    </span>
                  </div>
                  <span className="smi-muted smi-mono">{formatRelative(a.started_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="smi-card">
        <div className="smi-card-title-row">
          <div className="smi-card-title" style={{ margin: 0 }}>Servidores monitorados <span className="smi-muted">— CPU nas últimas 6 h</span></div>
          <Link className="smi-link" to="/servidores">Ver todos <ChevronRight size={14} /></Link>
        </div>
        {servers.data ? (
          <div className="smi-servergrid-mini">
            {servers.data.items.map((s) => <MiniServerCard key={s.id} server={s} />)}
          </div>
        ) : servers.error ? (
          <ErrorBox error={servers.error} onRetry={servers.reload} />
        ) : (
          <Loading />
        )}
      </div>
    </div>
  );
}

function MiniServerCard({ server }) {
  const series = useApi(
    (signal) => api.metrics(server.id, { metric: "cpu", range: "6h" }, { signal }),
    ["mini", server.id],
    { interval: SERIES_INTERVAL },
  );
  const color = server.metrics.cpu.status === "critical" ? STATUS.critical.color : METRIC_META.cpu.color;

  return (
    <Link className="smi-minicard" to={`/servidores/${server.id}`}>
      <div className="smi-minicard-head">
        <Led status={server.status} pulse />
        <span className="smi-mono">{server.name}</span>
      </div>
      <span className="smi-muted smi-minicard-role">{server.role}</span>
      <MiniChart data={series.data?.items[0].points} color={color} />
    </Link>
  );
}
