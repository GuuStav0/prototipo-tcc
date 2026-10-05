import { STATUS } from "../../config/status";
import { METRIC_META } from "../../config/metrics";
import { formatMetric } from "../../utils/format";
import "./MetricBar.css";

// reading = { value, status } vindo de Server.metrics[metric] na API.
// A cor segue o status calculado pelo motor de gatilhos, não um limite fixo na tela.
export default function MetricBar({ metric, reading }) {
  const meta = METRIC_META[metric];
  const value = reading?.value;
  const status = reading?.status ?? "unknown";
  const pct = value === null || value === undefined ? 0 : Math.min(100, (value / meta.max) * 100);
  const tone =
    status === "critical" || status === "warning" ? STATUS[status].color : status === "ok" ? meta.color : STATUS.unknown.color;

  return (
    <div className="smi-metricbar">
      <div className="smi-metricbar-head">
        <span><meta.icon size={12} strokeWidth={2.2} /> {meta.label}</span>
        <span className="smi-mono" style={status === "critical" || status === "warning" ? { color: tone } : undefined}>
          {formatMetric(metric, value)}
        </span>
      </div>
      <div className="smi-metricbar-track">
        <div className="smi-metricbar-fill" style={{ width: `${pct}%`, background: tone, opacity: status === "unknown" ? 0.5 : 1 }} />
      </div>
    </div>
  );
}
