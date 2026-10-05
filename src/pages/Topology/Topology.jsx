import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { LIVE_INTERVAL, useApi } from "../../hooks/useApi";
import { STATUS } from "../../config/status";
import { formatMetric } from "../../utils/format";
import Led from "../../components/Led/Led";
import { ErrorBox, Loading } from "../../components/Feedback/Feedback";

export default function Topology() {
  const [hover, setHover] = useState(null);
  const navigate = useNavigate();
  const { data, error, reload } = useApi((signal) => api.servers(undefined, { signal }), ["servers"], { interval: LIVE_INTERVAL });
  const cx = 300, cy = 200, r = 150;

  if (!data) return error ? <ErrorBox error={error} onRetry={reload} /> : <Loading />;
  const servers = data.items;
  const pos = (i) => {
    const angle = (i / servers.length) * Math.PI * 2 - Math.PI / 2;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  };
  const hovered = servers.find((s) => s.id === hover);

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title">Topologia de infraestrutura <span className="smi-muted">— mapa de rede (estilo Zabbix Maps)</span></div>
        <div className="smi-topo-wrap">
          <svg viewBox="0 0 600 400" className="smi-topo-svg">
            {servers.map((s, i) => {
              const [x, y] = pos(i);
              return <line key={s.id} x1={cx} y1={cy} x2={x} y2={y} stroke={hover === s.id ? STATUS[s.status].color : "#232B38"} strokeWidth={hover === s.id ? 2 : 1.2} />;
            })}
            <circle cx={cx} cy={cy} r={30} fill="#131822" stroke="#3B4658" strokeWidth={1.5} />
            <text x={cx} y={cy - 2} textAnchor="middle" fill="#E8ECF2" fontSize="11" fontFamily="JetBrains Mono, monospace">Núcleo</text>
            <text x={cx} y={cy + 11} textAnchor="middle" fill="#6B7690" fontSize="9" fontFamily="JetBrains Mono, monospace">switch</text>
            {servers.map((s, i) => {
              const [x, y] = pos(i);
              const st = STATUS[s.status];
              return (
                <g
                  key={s.id}
                  transform={`translate(${x},${y})`}
                  className={"smi-topo-node" + (s.status === "critical" ? " smi-topo-pulse" : "")}
                  onMouseEnter={() => setHover(s.id)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => navigate(`/servidores/${s.id}`)}
                >
                  <circle r={20} fill="#131822" stroke={st.color} strokeWidth={2} strokeDasharray={s.status === "unknown" ? "4 3" : undefined} />
                  <circle r={4} fill={st.color} />
                  <text y={34} textAnchor="middle" fill="#B8C0D2" fontSize="10" fontFamily="JetBrains Mono, monospace">{s.name}</text>
                </g>
              );
            })}
          </svg>
          {hovered && (
            <div className="smi-topo-tip">
              <div className="smi-detailhead-title" style={{ fontSize: 13 }}><Led status={hovered.status} /> {hovered.name}</div>
              <div className="smi-muted smi-mono" style={{ fontSize: 11.5 }}>{hovered.role} · {hovered.address}</div>
              <div className="smi-muted smi-mono" style={{ fontSize: 11.5 }}>
                CPU {formatMetric("cpu", hovered.metrics.cpu.value)} · Temp {formatMetric("temp", hovered.metrics.temp.value)} ·{" "}
                {formatMetric("reachable", hovered.metrics.reachable.value)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
