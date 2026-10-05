import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, ChevronRight, Download, Plus } from "lucide-react";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { REPORT_AUTHOR, REPORT_STATUS, REPORT_TYPES } from "../../config/status";
import { formatDateTime, formatPeriod, formatRelative } from "../../utils/format";
import { Empty, ErrorBox, Loading } from "../../components/Feedback/Feedback";
import "./Reports.css";

const PERIODS = [
  { id: "24h", label: "Últimas 24 horas" },
  { id: "7d", label: "Últimos 7 dias" },
  { id: "30d", label: "Últimos 30 dias" },
];

export default function Reports() {
  // enquanto houver relatório sendo gerado, consulta a cada 2 s
  const [pending, setPending] = useState(false);
  const reports = useApi(
    async (signal) => {
      const data = await api.reports({ signal });
      setPending(data.items.some((r) => r.status === "pending"));
      return data;
    },
    ["reports"],
    { interval: pending ? 2000 : 30_000 },
  );
  const [showForm, setShowForm] = useState(false);
  const [openId, setOpenId] = useState(null);

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title-row">
          <div className="smi-card-title" style={{ margin: 0 }}>Relatórios</div>
          <button className="smi-btn" onClick={() => setShowForm((v) => !v)}><Plus size={14} /> Gerar novo relatório</button>
        </div>
        <p className="smi-muted" style={{ fontSize: 12.5, marginTop: 0 }}>
          Gerados a partir dos dados coletados e do histórico de alertas. Na etapa 4 o texto passa a ser redigido pela IA via MCP.
        </p>

        {showForm && (
          <ReportForm
            onCreated={(r) => { setShowForm(false); setOpenId(r.id); setPending(true); reports.reload(); }}
          />
        )}

        {!reports.data ? (
          reports.error ? <ErrorBox error={reports.error} onRetry={reports.reload} /> : <Loading />
        ) : reports.data.items.length === 0 ? (
          <Empty>Nenhum relatório gerado ainda.</Empty>
        ) : (
          <div className="smi-table-wrap">
            <table className="smi-table">
              <thead><tr><th></th><th>Relatório</th><th>Tipo</th><th>Período</th><th>Gerado</th><th>Por</th><th>Status</th></tr></thead>
              <tbody>
                {reports.data.items.map((r) => (
                  <ReportRow
                    key={r.id}
                    report={r}
                    open={openId === r.id}
                    onToggle={() => setOpenId(openId === r.id ? null : r.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportForm({ onCreated }) {
  const [type, setType] = useState("availability");
  const [range, setRange] = useState("7d");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onCreated(await api.createReport({ type, range, requested_by: "Usuário do painel" }));
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <form className="smi-form" onSubmit={submit}>
      <div className="smi-form-row">
        <label>Tipo
          <select className="smi-select" value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(REPORT_TYPES).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </label>
        <label>Período
          <select className="smi-select" value={range} onChange={(e) => setRange(e.target.value)}>
            {PERIODS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
      </div>
      {error && <div className="smi-feedback smi-feedback-error" style={{ padding: 0 }}>{error}</div>}
      <button type="submit" className="smi-btn" disabled={saving} style={{ alignSelf: "flex-start" }}>
        {saving ? "Enviando…" : "Confirmar geração"}
      </button>
    </form>
  );
}

function ReportRow({ report: r, open, onToggle }) {
  const ready = r.status === "ready";
  return (
    <>
      <tr className={ready ? "smi-report-row" : ""} onClick={ready ? onToggle : undefined}>
        <td>{ready && (open ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}</td>
        <td>{r.title}</td>
        <td className="smi-muted">{REPORT_TYPES[r.type]}</td>
        <td className="smi-mono smi-muted">{formatPeriod(r.period_from, r.period_to)}</td>
        <td className="smi-mono smi-muted" title={formatDateTime(r.created_at)}>{formatRelative(r.created_at)}</td>
        <td className="smi-muted">{REPORT_AUTHOR[r.generated_by]}</td>
        <td>
          <span className={"smi-pill " + (r.status === "failed" ? "smi-pill-active" : r.status === "ready" ? "smi-pill-resolved" : "smi-pill-pending")}>
            {REPORT_STATUS[r.status]}
          </span>
        </td>
      </tr>
      {open && ready && (
        <tr>
          <td colSpan={7} className="smi-report-cell">
            <ReportContent id={r.id} />
          </td>
        </tr>
      )}
    </>
  );
}

function ReportContent({ id }) {
  const { data, error, reload } = useApi((signal) => api.report(id, { signal }), ["report", id]);
  if (!data) return error ? <ErrorBox error={error} onRetry={reload} /> : <Loading />;

  function download() {
    const blob = new Blob([data.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `relatorio-${data.type}-${data.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="smi-report">
      <div className="smi-report-actions">
        <span className="smi-muted">{data.summary}</span>
        <button className="smi-btn" onClick={download}><Download size={14} /> Baixar (.md)</button>
      </div>
      <div className="smi-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.content}</ReactMarkdown>
      </div>
    </div>
  );
}
