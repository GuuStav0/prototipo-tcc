import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { SERVERS, STATUS, METRIC_META, seriesFor } from "../../data/mockData";
import MetricBar from "../../components/MetricBar/MetricBar";
import BigChart from "../../components/charts/BigChart";

export default function Metrics() {
  const [hostId, setHostId] = useState(SERVERS[5].id);
  const [metric, setMetric] = useState("cpu");
  const host = SERVERS.find((s) => s.id === hostId);

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title">Dados em tempo real <span className="smi-muted">— coleta via SNMP / IPMI</span></div>
        <div className="smi-selrow">
          <select className="smi-select" value={hostId} onChange={(e) => setHostId(e.target.value)}>
            {SERVERS.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.role}</option>)}
          </select>
          <div className="smi-chipfilter">
            {Object.entries(METRIC_META).map(([k, m]) => (
              <button key={k} className={"smi-chip" + (metric === k ? " smi-chip-active" : "")} onClick={() => setMetric(k)}>
                <m.icon size={12} /> {m.label}
              </button>
            ))}
          </div>
        </div>
        <BigChart data={seriesFor(hostId, metric)} color={METRIC_META[metric].color} unit={METRIC_META[metric].unit} />
        <div className="smi-metricrow" style={{ marginTop: 4 }}>
          <MetricBar metric="cpu" value={host.cpu} />
          <MetricBar metric="ram" value={host.ram} />
          <MetricBar metric="disk" value={host.disk} />
          <MetricBar metric="temp" value={host.temp} />
        </div>
      </div>

      <div className="smi-card">
        <div className="smi-card-title">Comparativo de CPU entre servidores</div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart margin={{ top: 8, right: 16, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="#20293A" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="t" type="category" allowDuplicatedCategory={false} tick={{ fill: "#6B7690", fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={{ stroke: "#20293A" }} tickLine={false} interval={3} />
            <YAxis tick={{ fill: "#6B7690", fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} width={30} />
            <Tooltip contentStyle={{ background: "#111726", border: "1px solid #26314d", borderRadius: 8, fontFamily: "JetBrains Mono, monospace", fontSize: 12 }} />
            {SERVERS.slice(0, 6).map((s, i) => (
              <Line
                key={s.id}
                data={seriesFor(s.id, "cpu")}
                dataKey="v"
                name={s.name}
                dot={false}
                strokeWidth={1.6}
                stroke={s.status === "critical" ? STATUS.critical.color : ["#7DD3FC", "#A78BFA", "#34D399", "#FBBF24", "#F472B6", "#60A5FA"][i % 6]}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
