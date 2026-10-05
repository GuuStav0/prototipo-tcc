import { useState } from "react";
import { Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { api } from "../../api/client";
import { LIVE_INTERVAL, useApi } from "../../hooks/useApi";
import { STATUS } from "../../config/status";
import { DETECTION_TARGET_SECONDS, worstCaseDetection } from "../../config/metrics";
import { formatDuration } from "../../utils/format";
import { describeRule } from "../../utils/rules";
import AlertTable from "../../components/AlertTable/AlertTable";
import { Empty, ErrorBox, Loading } from "../../components/Feedback/Feedback";
import RuleForm from "./RuleForm";

const STATUS_FILTERS = [
  { id: "active", label: "Ativos" },
  { id: "resolved", label: "Resolvidos" },
  { id: "", label: "Todos" },
];
const SEVERITY_FILTERS = [
  { id: "", label: "Qualquer severidade" },
  { id: "critical", label: STATUS.critical.label },
  { id: "warning", label: STATUS.warning.label },
];
const LIMIT = 100;

export default function Triggers() {
  return (
    <div className="smi-stack">
      <AlertsCard />
      <RulesCard />
    </div>
  );
}

function AlertsCard() {
  const [status, setStatus] = useState("active");
  const [severity, setSeverity] = useState("");
  const alerts = useApi(
    (signal) => api.alerts({ status, severity, limit: LIMIT }, { signal }),
    ["alerts", status, severity],
    { interval: LIVE_INTERVAL },
  );

  return (
    <div className="smi-card">
      <div className="smi-card-title">Alertas</div>
      <div className="smi-chipfilter" style={{ marginTop: 0, marginBottom: 12 }}>
        {STATUS_FILTERS.map((f) => (
          <button key={f.id} className={"smi-chip" + (status === f.id ? " smi-chip-active" : "")} onClick={() => setStatus(f.id)}>
            {f.label}
          </button>
        ))}
        <span style={{ width: 10 }} />
        {SEVERITY_FILTERS.map((f) => (
          <button key={f.id} className={"smi-chip" + (severity === f.id ? " smi-chip-active" : "")} onClick={() => setSeverity(f.id)}>
            {f.label}
          </button>
        ))}
      </div>
      {alerts.data ? (
        alerts.data.items.length ? (
          <>
            <AlertTable alerts={alerts.data.items} actions onChanged={alerts.reload} />
            {alerts.data.total > alerts.data.items.length && (
              <div className="smi-muted" style={{ fontSize: 11.5, marginTop: 10 }}>
                Mostrando os {alerts.data.items.length} mais recentes de {alerts.data.total}.
              </div>
            )}
          </>
        ) : (
          <Empty>Nenhum alerta com esses filtros.</Empty>
        )
      ) : alerts.error ? (
        <ErrorBox error={alerts.error} onRetry={alerts.reload} />
      ) : (
        <Loading />
      )}
    </div>
  );
}

function RulesCard() {
  const rules = useApi((signal) => api.triggers(undefined, { signal }), ["rules"]);
  const servers = useApi((signal) => api.servers(undefined, { signal }), ["servers-select"]);
  const [editing, setEditing] = useState(null); // null | "new" | regra
  const [error, setError] = useState(null);

  async function run(action) {
    setError(null);
    try {
      await action();
      rules.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  function remove(rule) {
    if (!window.confirm(`Remover a regra "${rule.name}"? Os alertas antigos continuam no histórico.`)) return;
    run(() => api.deleteTrigger(rule.id));
  }

  return (
    <div className="smi-card">
      <div className="smi-card-title-row">
        <div className="smi-card-title" style={{ margin: 0 }}>Regras do motor de gatilhos</div>
        {editing === null && (
          <button className="smi-btn" onClick={() => setEditing("new")}><Plus size={14} /> Nova regra</button>
        )}
      </div>
      <p className="smi-muted" style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 760, marginTop: 0 }}>
        Cada regra compara uma métrica coletada a dois limiares e classifica o host em{" "}
        <b style={{ color: STATUS.ok.color }}>OK</b>, <b style={{ color: STATUS.warning.color }}>Aviso</b> ou{" "}
        <b style={{ color: STATUS.critical.color }}>Crítico</b>. O alerta só dispara (e só resolve) depois que a condição se
        mantém pela duração configurada. Regras globais valem para todos os hosts; uma regra específica substitui a global
        da mesma métrica naquele host.
      </p>

      {editing !== null && (
        <RuleForm
          key={editing === "new" ? "new" : editing.id}
          rule={editing === "new" ? undefined : editing}
          servers={servers.data?.items ?? []}
          onSaved={() => { setEditing(null); rules.reload(); }}
          onCancel={() => setEditing(null)}
        />
      )}
      {error && <ErrorBox error={{ message: error }} />}

      {rules.data ? (
        <div className="smi-table-wrap">
          <table className="smi-table">
            <thead>
              <tr><th>Regra</th><th>Condição</th><th>Duração</th><th>Escopo</th><th>Ativa</th><th></th></tr>
            </thead>
            <tbody>
              {rules.data.items.map((r) => {
                const slow = worstCaseDetection(r.duration_seconds) > DETECTION_TARGET_SECONDS;
                return (
                  <tr key={r.id} className={r.enabled ? "" : "smi-row-dim"}>
                    <td>{r.name}</td>
                    <td className="smi-mono smi-muted">{describeRule(r)}</td>
                    <td className="smi-mono smi-muted">
                      {formatDuration(r.duration_seconds)}
                      {slow && (
                        <span title={`Pior caso de detecção acima da meta de ${DETECTION_TARGET_SECONDS} s`} style={{ color: STATUS.warning.color, marginLeft: 6 }}>
                          <TriangleAlert size={12} />
                        </span>
                      )}
                    </td>
                    <td className="smi-mono smi-muted">{r.host_id ?? "global"}</td>
                    <td>
                      <button
                        className={"smi-chip" + (r.enabled ? " smi-chip-active" : "")}
                        onClick={() => run(() => api.updateTrigger(r.id, { enabled: !r.enabled }))}
                      >
                        {r.enabled ? "Ativa" : "Inativa"}
                      </button>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                        <button className="smi-icon-btn" title="Editar" onClick={() => setEditing(r)}><Pencil size={14} /></button>
                        <button className="smi-icon-btn" title="Remover" onClick={() => remove(r)}><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : rules.error ? (
        <ErrorBox error={rules.error} onRetry={rules.reload} />
      ) : (
        <Loading />
      )}
    </div>
  );
}
