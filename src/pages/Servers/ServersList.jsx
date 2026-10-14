import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronRight, Plus } from "lucide-react";
import { api } from "../../api/client";
import { LIVE_INTERVAL, useApi } from "../../hooks/useApi";
import { STATUS, STATUS_ORDER } from "../../config/status";
import { CHART_METRICS } from "../../config/metrics";
import { formatRelative } from "../../utils/format";
import Led from "../../components/Led/Led";
import StatusBadge from "../../components/StatusBadge/StatusBadge";
import MetricBar from "../../components/MetricBar/MetricBar";
import { Empty, ErrorBox, Loading } from "../../components/Feedback/Feedback";
import ModeBadge from "../../components/ModeBadge/ModeBadge";
import ServerForm from "./ServerForm";

const MODES = [
  { id: "all", label: "Todos" },
  { id: "real", label: "Reais" },
  { id: "simulated", label: "Simulados" },
];

const rank = Object.fromEntries(STATUS_ORDER.map((s, i) => [s, i]));

export default function ServersList() {
  const [filter, setFilter] = useState("all");
  const [mode, setMode] = useState("all");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();
  const { data, error, reload } = useApi((signal) => api.servers(undefined, { signal }), ["servers"], { interval: LIVE_INTERVAL });

  if (!data) return error ? <ErrorBox error={error} onRetry={reload} /> : <Loading />;

  const inMode = data.items.filter((s) => mode === "all" || s.mode === mode);
  // mais graves primeiro
  const servers = [...inMode]
    .filter((s) => filter === "all" || s.status === filter)
    .sort((a, b) => rank[a.status] - rank[b.status] || a.id.localeCompare(b.id));
  const counts = Object.fromEntries(STATUS_ORDER.map((s) => [s, inMode.filter((x) => x.status === s).length]));
  const modeCounts = { all: data.items.length, real: data.items.filter((s) => s.mode === "real").length,
    simulated: data.items.filter((s) => s.mode === "simulated").length };

  return (
    <div className="smi-stack">
      <div className="smi-selrow" style={{ marginBottom: 0 }}>
        <div className="smi-chipfilter" style={{ marginTop: 0 }}>
          {MODES.map((m) => (
            <button key={m.id} className={"smi-chip" + (mode === m.id ? " smi-chip-active" : "")} onClick={() => setMode(m.id)}>
              {m.label} · {modeCounts[m.id]}
            </button>
          ))}
        </div>
        {!creating && (
          <button className="smi-btn" onClick={() => setCreating(true)}><Plus size={14} /> Cadastrar servidor</button>
        )}
      </div>

      {creating && (
        <ServerForm
          onCreated={(s) => navigate(`/servidores/${s.id}?novo=1`)}
          onCancel={() => setCreating(false)}
        />
      )}

      <div className="smi-chipfilter" style={{ marginTop: 0 }}>
        <button className={"smi-chip" + (filter === "all" ? " smi-chip-active" : "")} onClick={() => setFilter("all")}>
          Qualquer estado · {inMode.length}
        </button>
        {STATUS_ORDER.map((s) => (
          <button key={s} className={"smi-chip" + (filter === s ? " smi-chip-active" : "")} onClick={() => setFilter(s)}>
            <Led status={s} size={7} /> {STATUS[s].label} · {counts[s]}
          </button>
        ))}
      </div>

      {servers.length === 0 ? (
        <div className="smi-card">
          <Empty>{mode === "real" && !modeCounts.real ? "Nenhum servidor real cadastrado ainda. Use \"Cadastrar servidor\"." : "Nenhum servidor neste filtro."}</Empty>
        </div>
      ) : (
        <div className="smi-servergrid">
          {servers.map((s) => (
            <div key={s.id} className="smi-card smi-servercard">
              <div className="smi-detailhead">
                <div>
                  <div className="smi-detailhead-title" style={{ fontSize: 14 }}><Led status={s.status} pulse /> {s.name}</div>
                  <div className="smi-muted smi-mono" style={{ fontSize: 11.5 }}>{s.role}</div>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <ModeBadge mode={s.mode} />
                  <StatusBadge status={s.status} />
                </div>
              </div>
              <div className="smi-muted smi-mono" style={{ fontSize: 11.5, marginTop: 2 }}>
                {s.address} · {s.os} · última coleta {formatRelative(s.last_seen_at)}
              </div>
              <div className="smi-metricrow" style={{ marginTop: 10 }}>
                {CHART_METRICS.map((m) => <MetricBar key={m} metric={m} reading={s.metrics[m]} />)}
              </div>
              <Link className="smi-btn-ghost" to={`/servidores/${s.id}`}>Ver detalhes <ChevronRight size={14} /></Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
