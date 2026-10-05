import { useParams, useNavigate, Navigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { SERVERS, TRIGGERS, METRIC_META, seriesFor } from "../../data/mockData";
import Led from "../../components/Led/Led";
import StatusBadge from "../../components/StatusBadge/StatusBadge";
import MetricBar from "../../components/MetricBar/MetricBar";
import BigChart from "../../components/charts/BigChart";
import TriggerTable from "../../components/TriggerTable/TriggerTable";

export default function ServerDetail() {
  const { hostId } = useParams();
  const navigate = useNavigate();
  const host = SERVERS.find((s) => s.id === hostId);

  // hostId inexistente na URL -> volta para a listagem
  if (!host) return <Navigate to="/servidores" replace />;

  return (
    <div className="smi-stack">
      <button className="smi-back" onClick={() => navigate("/servidores")}>
        <ArrowLeft size={14} /> Voltar aos servidores
      </button>

      <div className="smi-card">
        <div className="smi-detailhead">
          <div>
            <div className="smi-detailhead-title"><Led status={host.status} pulse size={11} /> {host.name}</div>
            <div className="smi-muted smi-mono">{host.role} · {host.os} · {host.ip}</div>
          </div>
          <div className="smi-detailhead-right">
            <StatusBadge status={host.status} />
            <span className="smi-muted smi-mono">uptime {host.uptime}</span>
          </div>
        </div>
        <div className="smi-metricrow">
          <MetricBar metric="cpu" value={host.cpu} />
          <MetricBar metric="ram" value={host.ram} />
          <MetricBar metric="disk" value={host.disk} />
          <MetricBar metric="temp" value={host.temp} />
        </div>
      </div>

      <div className="smi-grid-2">
        {["cpu", "ram", "disk", "temp"].map((m) => (
          <div className="smi-card" key={m}>
            <div className="smi-card-title">{METRIC_META[m].label} — últimas 24h</div>
            <BigChart data={seriesFor(host.id, m)} color={METRIC_META[m].color} unit={METRIC_META[m].unit} />
          </div>
        ))}
      </div>

      <div className="smi-card">
        <div className="smi-card-title">Gatilhos relacionados a este host</div>
        <TriggerTable rows={TRIGGERS.filter((t) => t.host === host.id)} compact />
      </div>
    </div>
  );
}
