import { useState } from "react";
import { useParams, useNavigate, useSearchParams, Navigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "../../api/client";
import { LIVE_INTERVAL, SERIES_INTERVAL, useApi } from "../../hooks/useApi";
import { CHART_METRICS, METRIC_META, RANGES } from "../../config/metrics";
import { formatDuration, formatRelative, formatUptime } from "../../utils/format";
import { describeRule, rulesFor } from "../../utils/rules";
import Led from "../../components/Led/Led";
import StatusBadge from "../../components/StatusBadge/StatusBadge";
import MetricBar from "../../components/MetricBar/MetricBar";
import BigChart from "../../components/charts/BigChart";
import AlertTable from "../../components/AlertTable/AlertTable";
import { Empty, ErrorBox, Loading } from "../../components/Feedback/Feedback";
import ModeBadge from "../../components/ModeBadge/ModeBadge";
import ServerManage from "./ServerManage";

export default function ServerDetail() {
  const { hostId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [range, setRange] = useState("24h");

  const server = useApi((signal) => api.server(hostId, { signal }), ["server", hostId], { interval: LIVE_INTERVAL });
  const series = useApi(
    (signal) => api.metrics(hostId, { metric: CHART_METRICS.join(","), range }, { signal }),
    ["series", hostId, range],
    { interval: SERIES_INTERVAL },
  );
  const alerts = useApi((signal) => api.alerts({ host_id: hostId, limit: 20 }, { signal }), ["alerts", hostId], {
    interval: LIVE_INTERVAL,
  });
  const rules = useApi((signal) => api.triggers({ host_id: hostId }, { signal }), ["rules", hostId]);

  // hostId inexistente na URL -> volta para a listagem
  if (server.error?.status === 404) return <Navigate to="/servidores" replace />;
  if (!server.data) return server.error ? <ErrorBox error={server.error} onRetry={server.reload} /> : <Loading />;

  const host = server.data;
  const effectiveRules = rulesFor(rules.data?.items ?? [], hostId);

  return (
    <div className="smi-stack">
      <button className="smi-back" onClick={() => navigate("/servidores")}>
        <ArrowLeft size={14} /> Voltar aos servidores
      </button>

      <div className="smi-card">
        <div className="smi-detailhead">
          <div>
            <div className="smi-detailhead-title"><Led status={host.status} pulse size={11} /> {host.name}</div>
            <div className="smi-muted smi-mono">{host.role} · {host.os} · {host.address}</div>
          </div>
          <div className="smi-detailhead-right">
            <div style={{ display: "flex", gap: 6 }}>
              <ModeBadge mode={host.mode} />
              <StatusBadge status={host.status} />
            </div>
            <span className="smi-muted smi-mono">uptime {formatUptime(host.uptime_seconds)}</span>
            <span className="smi-muted smi-mono">última coleta {formatRelative(host.last_seen_at)}</span>
          </div>
        </div>
        <div className="smi-metricrow">
          {CHART_METRICS.map((m) => <MetricBar key={m} metric={m} reading={host.metrics[m]} />)}
        </div>
        {host.mode === "real" && host.last_seen_at && host.metrics.temp.value === null && (
          <div className="smi-muted" style={{ fontSize: 11.5, marginTop: 10 }}>
            Temperatura indisponível neste servidor (máquinas virtuais, como uma VPS, não têm sensores de hardware).
          </div>
        )}
      </div>

      <ServerManage host={host} isNew={params.get("novo") === "1"} onChanged={server.reload} />

      <div className="smi-chipfilter" style={{ marginTop: 0 }}>
        {RANGES.map((r) => (
          <button key={r.id} className={"smi-chip" + (range === r.id ? " smi-chip-active" : "")} onClick={() => setRange(r.id)}>
            {r.label}
          </button>
        ))}
      </div>

      <div className="smi-grid-2">
        {CHART_METRICS.map((m, i) => {
          const rule = effectiveRules.find((r) => r.metric === m);
          return (
            <div className="smi-card" key={m}>
              <div className="smi-card-title">
                {METRIC_META[m].label} <span className="smi-muted">— {RANGES.find((r) => r.id === range).label}</span>
              </div>
              {series.data ? (
                <BigChart
                  data={series.data.items[i].points}
                  color={METRIC_META[m].color}
                  unit={METRIC_META[m].symbol}
                  thresholds={rule ? { warning: rule.warning_threshold, critical: rule.critical_threshold } : undefined}
                />
              ) : series.error ? (
                <ErrorBox error={series.error} onRetry={series.reload} />
              ) : (
                <Loading />
              )}
            </div>
          );
        })}
      </div>

      <div className="smi-card">
        <div className="smi-card-title">Alertas deste host</div>
        {alerts.data ? (
          alerts.data.items.length ? (
            <AlertTable alerts={alerts.data.items} hideHost actions onChanged={alerts.reload} />
          ) : (
            <Empty>Nenhum alerta registrado para este host.</Empty>
          )
        ) : alerts.error ? (
          <ErrorBox error={alerts.error} onRetry={alerts.reload} />
        ) : (
          <Loading />
        )}
      </div>

      <div className="smi-card">
        <div className="smi-card-title">Regras aplicadas</div>
        <div className="smi-table-wrap">
          <table className="smi-table">
            <thead>
              <tr><th>Regra</th><th>Condição</th><th>Duração</th><th>Escopo</th></tr>
            </thead>
            <tbody>
              {effectiveRules.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td className="smi-mono smi-muted">{describeRule(r)}</td>
                  <td className="smi-mono smi-muted">{formatDuration(r.duration_seconds)}</td>
                  <td className="smi-muted">{r.host_id ? "específica deste host" : "global"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
