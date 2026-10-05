import { useState } from "react";
import { api } from "../../api/client";
import { DETECTION_TARGET_SECONDS, METRIC_META, OPERATORS, worstCaseDetection } from "../../config/metrics";

const EMPTY = {
  name: "",
  metric: "cpu",
  host_id: "",
  operator: "gt",
  warning_threshold: "",
  critical_threshold: "",
  duration_seconds: 60,
};

function toForm(rule) {
  if (!rule) return EMPTY;
  return {
    ...rule,
    host_id: rule.host_id ?? "",
    warning_threshold: rule.warning_threshold ?? "",
    critical_threshold: rule.critical_threshold ?? "",
  };
}

const num = (v) => (v === "" || v === null ? null : Number(v));

// Cria (rule = undefined) ou edita uma regra de gatilho
export default function RuleForm({ rule, servers, onSaved, onCancel }) {
  const [form, setForm] = useState(() => toForm(rule));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const worst = worstCaseDetection(Number(form.duration_seconds) || 0);

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const body = {
      name: form.name.trim(),
      metric: form.metric,
      host_id: form.host_id || null,
      operator: form.operator,
      warning_threshold: num(form.warning_threshold),
      critical_threshold: num(form.critical_threshold),
      duration_seconds: Number(form.duration_seconds),
    };
    try {
      if (rule) {
        // só o que mudou: alterar limiares/escopo reinicia a avaliação da regra no backend,
        // mas renomear não deve fechar os alertas abertos
        const changes = Object.fromEntries(Object.entries(body).filter(([k, v]) => v !== rule[k]));
        if (Object.keys(changes).length) await api.updateTrigger(rule.id, changes);
      } else {
        await api.createTrigger(body);
      }
      onSaved();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <form className="smi-form" onSubmit={submit}>
      <div className="smi-card-title" style={{ margin: 0 }}>{rule ? `Editar regra: ${rule.name}` : "Nova regra"}</div>
      <div className="smi-form-row">
        <label style={{ flex: 2 }}>Nome
          <input className="smi-select" required value={form.name} onChange={set("name")} placeholder="Ex.: CPU elevada no banco" />
        </label>
        <label>Métrica
          <select className="smi-select" value={form.metric} onChange={set("metric")}>
            {Object.entries(METRIC_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
          </select>
        </label>
        <label>Escopo
          <select className="smi-select" value={form.host_id} onChange={set("host_id")}>
            <option value="">Global (todos os hosts)</option>
            {servers.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
          </select>
        </label>
      </div>
      <div className="smi-form-row">
        <label>Operador
          <select className="smi-select" value={form.operator} onChange={set("operator")}>
            {Object.entries(OPERATORS).map(([k, sym]) => <option key={k} value={k}>{sym}</option>)}
          </select>
        </label>
        <label>Limiar de aviso {METRIC_META[form.metric].symbol && `(${METRIC_META[form.metric].symbol})`}
          <input className="smi-select" type="number" step="any" value={form.warning_threshold} onChange={set("warning_threshold")} placeholder="vazio = sem aviso" />
        </label>
        <label>Limiar crítico {METRIC_META[form.metric].symbol && `(${METRIC_META[form.metric].symbol})`}
          <input className="smi-select" type="number" step="any" value={form.critical_threshold} onChange={set("critical_threshold")} placeholder="vazio = sem crítico" />
        </label>
        <label>Duração (s)
          <input className="smi-select" type="number" min="0" required value={form.duration_seconds} onChange={set("duration_seconds")} />
        </label>
      </div>
      <div className={"smi-muted"} style={{ fontSize: 11.5, color: worst > DETECTION_TARGET_SECONDS ? "#FBBF24" : undefined }}>
        Pior caso de detecção: {worst} s (coleta 15 s + duração + atualização da tela 10 s)
        {worst > DETECTION_TARGET_SECONDS ? ` — acima da meta de ${DETECTION_TARGET_SECONDS} s do TCC` : ` — dentro da meta de ${DETECTION_TARGET_SECONDS} s`}
      </div>
      {error && <div className="smi-feedback smi-feedback-error" style={{ padding: 0 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="smi-btn" disabled={saving}>{saving ? "Salvando…" : rule ? "Salvar alterações" : "Criar regra"}</button>
        <button type="button" className="smi-btn" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}
