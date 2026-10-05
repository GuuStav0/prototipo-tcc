import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { api } from "../../api/client";
import { LIVE_INTERVAL, SERIES_INTERVAL, useApi } from "../../hooks/useApi";
import { CHART_METRICS, METRIC_META, RANGES } from "../../config/metrics";
import { axisTimeFormatter, formatDateTime, formatNumber } from "../../utils/format";
import { rulesFor } from "../../utils/rules";
import MetricBar from "../../components/MetricBar/MetricBar";
import BigChart from "../../components/charts/BigChart";
import { AXIS_TICK, TOOLTIP_STYLE } from "../../components/charts/series";
import { ErrorBox, Loading } from "../../components/Feedback/Feedback";

const COMPARE_COLORS = ["#7DD3FC", "#A78BFA", "#34D399", "#FBBF24", "#F472B6", "#60A5FA"];
const COMPARE_COUNT = 6;

export default function Metrics() {
  const servers = useApi((signal) => api.servers(undefined, { signal }), ["servers"], { interval: LIVE_INTERVAL });
  const [selected, setSelected] = useState(null);
  const [metric, setMetric] = useState("cpu");
  const [range, setRange] = useState("24h");

  if (!servers.data) return servers.error ? <ErrorBox error={servers.error} onRetry={servers.reload} /> : <Loading />;
  const list = servers.data.items;
  if (!list.length) return <div className="smi-card"><ErrorBox error={{ message: "Nenhum servidor cadastrado." }} /></div>;

  // padrão: o servidor em pior estado
  const order = { critical: 0, warning: 1, ok: 2, unknown: 3 };
  const hostId = selected ?? [...list].sort((a, b) => order[a.status] - order[b.status])[0].id;
  const host = list.find((s) => s.id === hostId) ?? list[0];

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title">Dados coletados <span className="smi-muted">— atualizados a cada 15 s</span></div>
        <div className="smi-selrow">
          <select className="smi-select" value={host.id} onChange={(e) => setSelected(e.target.value)}>
            {list.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.role}</option>)}
          </select>
          <div className="smi-chipfilter" style={{ marginTop: 0 }}>
            {CHART_METRICS.map((k) => {
              const m = METRIC_META[k];
              return (
                <button key={k} className={"smi-chip" + (metric === k ? " smi-chip-active" : "")} onClick={() => setMetric(k)}>
                  <m.icon size={12} /> {m.label}
                </button>
              );
            })}
            <span style={{ width: 8 }} />
            {RANGES.map((r) => (
              <button key={r.id} className={"smi-chip" + (range === r.id ? " smi-chip-active" : "")} onClick={() => setRange(r.id)}>
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <HostChart hostId={host.id} metric={metric} range={range} />
        <div className="smi-metricrow" style={{ marginTop: 4 }}>
          {CHART_METRICS.map((m) => <MetricBar key={m} metric={m} reading={host.metrics[m]} />)}
        </div>
      </div>

      <CompareCard servers={list} metric={metric} range={range} />
    </div>
  );
}

function HostChart({ hostId, metric, range }) {
  const series = useApi((signal) => api.metrics(hostId, { metric, range }, { signal }), ["series", hostId, metric, range], {
    interval: SERIES_INTERVAL,
  });
  const rules = useApi((signal) => api.triggers({ host_id: hostId, metric }, { signal }), ["rules", hostId, metric]);
  const rule = rulesFor(rules.data?.items ?? [], hostId)[0];

  if (!series.data) return series.error ? <ErrorBox error={series.error} onRetry={series.reload} /> : <Loading />;
  return (
    <BigChart
      data={series.data.items[0].points}
      color={METRIC_META[metric].color}
      unit={METRIC_META[metric].symbol}
      thresholds={rule ? { warning: rule.warning_threshold, critical: rule.critical_threshold } : undefined}
    />
  );
}

// Compara a métrica entre os servidores com maior valor atual (no máximo 6 linhas,
// para o gráfico continuar legível)
function CompareCard({ servers, metric, range }) {
  const top = [...servers]
    .filter((s) => s.metrics[metric].value !== null)
    .sort((a, b) => b.metrics[metric].value - a.metrics[metric].value)
    .slice(0, COMPARE_COUNT)
    .map((s) => s.id)
    .sort(); // ordem estável: a consulta só refaz se o grupo mudar, e as cores não trocam

  const series = useApi(
    async (signal) => {
      const results = await Promise.all(top.map((id) => api.metrics(id, { metric, range }, { signal })));
      // junta as séries numa tabela { t, "srv-a": v, "srv-b": v, ... } para o gráfico de linhas
      const rows = new Map();
      results.forEach((r, i) => {
        for (const p of r.items[0].points) {
          const ts = Date.parse(p.t);
          if (!rows.has(ts)) rows.set(ts, { ts });
          rows.get(ts)[top[i]] = p.v;
        }
      });
      return [...rows.values()].sort((a, b) => a.ts - b.ts);
    },
    ["compare", metric, range, top],
    { interval: SERIES_INTERVAL },
  );

  const meta = METRIC_META[metric];
  const data = series.data ?? [];
  const span = data.length > 1 ? data.at(-1).ts - data[0].ts : 0;

  return (
    <div className="smi-card">
      <div className="smi-card-title">
        Comparativo — {meta.label} <span className="smi-muted">— {top.length} servidores com maior valor atual</span>
      </div>
      {!series.data ? (
        series.error ? <ErrorBox error={series.error} onRetry={series.reload} /> : <Loading />
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#20293A" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={AXIS_TICK} tickFormatter={axisTimeFormatter(span)} axisLine={{ stroke: "#20293A" }} tickLine={false} minTickGap={40} />
            <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={50} unit={meta.symbol} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={formatDateTime}
              formatter={(v, name) => [v === null || v === undefined ? "sem dados" : `${formatNumber(v)}${meta.symbol}`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} />
            {top.map((id, i) => (
              <Line key={id} dataKey={id} name={id} dot={false} connectNulls strokeWidth={1.6} stroke={COMPARE_COLORS[i % COMPARE_COLORS.length]} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
