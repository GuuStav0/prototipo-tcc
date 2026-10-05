import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../../api/client";
import { ALERT_STATUS, STATUS } from "../../config/status";
import { METRIC_META } from "../../config/metrics";
import { formatDateTime, formatDuration, formatMetric, formatRelative } from "../../utils/format";
import Led from "../Led/Led";
import "./AlertTable.css";

function duration(a) {
  const end = a.resolved_at ? new Date(a.resolved_at) : Date.now();
  return formatDuration((end - new Date(a.started_at)) / 1000);
}

// alerts = itens de GET /alerts. Com `actions`, mostra reconhecer e verdadeiro/falso positivo.
export default function AlertTable({ alerts, hideHost = false, actions = false, onChanged }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  async function patch(alert, body) {
    setBusy(alert.id);
    setError(null);
    try {
      await api.updateAlert(alert.id, body);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="smi-table-wrap">
      {error && <div className="smi-feedback smi-feedback-error">{error}</div>}
      <table className="smi-table">
        <thead>
          <tr>
            <th></th>
            <th>Gatilho</th>
            {!hideHost && <th>Host</th>}
            <th>Valor</th>
            <th>Início</th>
            <th>Status</th>
            {actions && <th>Avaliação</th>}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => {
            const active = a.status === "active";
            return (
              <tr key={a.id} className={active ? "" : "smi-row-dim"}>
                <td>
                  <Led status={active ? a.severity : a.peak_severity} pulse={active && a.severity === "critical"} />
                </td>
                <td>
                  <div>{a.trigger_name}</div>
                  <div className="smi-muted smi-mono smi-cell-sub">
                    {METRIC_META[a.metric]?.label} · {STATUS[active ? a.severity : a.peak_severity].label}
                  </div>
                </td>
                {!hideHost && (
                  <td className="smi-mono">
                    <Link className="smi-link-plain" to={`/servidores/${a.host_id}`}>{a.host_id}</Link>
                  </td>
                )}
                <td className="smi-mono">
                  {formatMetric(a.metric, a.value_last)}
                  {a.value_peak !== a.value_last && (
                    <div className="smi-muted smi-cell-sub">pico {formatMetric(a.metric, a.value_peak)}</div>
                  )}
                </td>
                <td className="smi-mono smi-muted" title={formatDateTime(a.started_at)}>
                  {formatRelative(a.started_at)}
                </td>
                <td>
                  <span className={"smi-pill " + (active ? "smi-pill-active" : "smi-pill-resolved")}>{ALERT_STATUS[a.status]}</span>
                  <div className="smi-muted smi-mono smi-cell-sub">{duration(a)}</div>
                </td>
                {actions && (
                  <td>
                    <div className="smi-alert-actions">
                      <button
                        className={"smi-chip" + (a.acknowledged_at ? " smi-chip-active" : "")}
                        disabled={busy === a.id}
                        onClick={() => patch(a, { acknowledged: !a.acknowledged_at })}
                        title={a.acknowledged_at ? `Reconhecido ${formatRelative(a.acknowledged_at)}` : "Marcar como reconhecido pela equipe"}
                      >
                        <Check size={12} /> {a.acknowledged_at ? "Reconhecido" : "Reconhecer"}
                      </button>
                      <button
                        className={"smi-chip smi-chip-icon" + (a.validation === "true_positive" ? " smi-chip-ok" : "")}
                        disabled={busy === a.id}
                        onClick={() => patch(a, { validation: a.validation === "true_positive" ? null : "true_positive" })}
                        title="Alerta verdadeiro (precisão dos alertas, TCC 4.5)"
                      >
                        <ThumbsUp size={12} />
                      </button>
                      <button
                        className={"smi-chip smi-chip-icon" + (a.validation === "false_positive" ? " smi-chip-bad" : "")}
                        disabled={busy === a.id}
                        onClick={() => patch(a, { validation: a.validation === "false_positive" ? null : "false_positive" })}
                        title="Falso positivo (precisão dos alertas, TCC 4.5)"
                      >
                        <ThumbsDown size={12} />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
