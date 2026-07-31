import React from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { SERVERS } from "../../data/mockData";
import Led from "../../components/Led/Led";
import StatusBadge from "../../components/StatusBadge/StatusBadge";
import MetricBar from "../../components/MetricBar/MetricBar";

export default function ServersList() {
  return (
    <div className="smi-stack">
      <div className="smi-servergrid">
        {SERVERS.map((s) => (
          <div key={s.id} className="smi-card smi-servercard">
            <div className="smi-detailhead">
              <div>
                <div className="smi-detailhead-title" style={{ fontSize: 14 }}><Led status={s.status} pulse /> {s.name}</div>
                <div className="smi-muted smi-mono" style={{ fontSize: 11.5 }}>{s.role}</div>
              </div>
              <StatusBadge status={s.status} />
            </div>
            <div className="smi-muted smi-mono" style={{ fontSize: 11.5, marginTop: 2 }}>{s.ip} · {s.os}</div>
            <div className="smi-metricrow" style={{ marginTop: 10 }}>
              <MetricBar metric="cpu" value={s.cpu} />
              <MetricBar metric="ram" value={s.ram} />
              <MetricBar metric="disk" value={s.disk} />
              <MetricBar metric="temp" value={s.temp} />
            </div>
            <Link className="smi-btn-ghost" to={`/servidores/${s.id}`}>Ver detalhes <ChevronRight size={14} /></Link>
          </div>
        ))}
      </div>
    </div>
  );
}
