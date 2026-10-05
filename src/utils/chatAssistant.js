// Assistente SIMULADO: respostas montadas por palavra-chave, mas com dados reais da API.
// Na etapa 4 isto é substituído pelo LLM conectado ao servidor MCP (POST /assistant/messages).
import { formatDuration, formatMetric, formatPercent, formatRelative } from "./format";
import { describeRule } from "./rules";
import { STATUS } from "../config/status";

export const SUGGESTIONS = [
  "Resumo de disponibilidade de hoje",
  "Qual servidor está em pior estado?",
  "Gerar relatório semanal de incidentes",
  "Quais alertas estão ativos?",
];

const ORDER = { critical: 0, warning: 1, ok: 2, unknown: 3 };

function hostSummary(s) {
  const m = s.metrics;
  return `CPU ${formatMetric("cpu", m.cpu.value)}, memória ${formatMetric("ram", m.ram.value)}, disco ${formatMetric("disk", m.disk.value)}, temperatura ${formatMetric("temp", m.temp.value)}`;
}

// ctx = { servers, overview, alerts, rules } vindos da API
export function buildAnswer(text, { servers, overview, alerts, rules }) {
  const q = text.toLowerCase();
  const byStatus = (st) => servers.filter((s) => s.status === st);
  const named = servers.find((s) => q.includes(s.id) || q.includes(s.id.replace("srv-", "")));

  if (named) {
    const hostAlerts = alerts.filter((a) => a.host_id === named.id);
    const lines = hostAlerts.map(
      (a) => `${a.trigger_name} (${a.severity === "critical" ? "crítico" : "aviso"}, ${formatMetric(a.metric, a.value_last)}, desde ${formatRelative(a.started_at)})`,
    );
    const hostRules = rules.filter((r) => r.enabled && (r.host_id === null || r.host_id === named.id));
    return {
      tool: `api.servers.get("${named.id}") + api.alerts.list(host_id="${named.id}", status="active")`,
      text:
        `${named.id} (${named.role}) está com status "${STATUS[named.status].label}". Valores atuais: ${hostSummary(named)}. ` +
        (lines.length ? `Alertas ativos: ${lines.join("; ")}. ` : "Nenhum alerta ativo. ") +
        (hostRules.length ? `Regras avaliadas: ${hostRules.map((r) => describeRule(r)).join("; ")}.` : ""),
    };
  }

  if (q.includes("pior") || q.includes("crítico") || q.includes("critico")) {
    const worst = [...servers].sort((a, b) => ORDER[a.status] - ORDER[b.status] || b.active_alerts.critical - a.active_alerts.critical)[0];
    if (!worst || worst.status === "ok") {
      return { tool: "api.servers.list()", text: "Nenhum servidor está em aviso ou crítico no momento." };
    }
    return {
      tool: "api.servers.list(sort=status)",
      text: `O servidor em pior estado é o ${worst.id} (${STATUS[worst.status].label.toLowerCase()}), com ${worst.active_alerts.critical} alerta(s) crítico(s) e ${worst.active_alerts.warning} aviso(s). ${hostSummary(worst)}. Pergunte "e o ${worst.id}?" para ver os detalhes.`,
    };
  }

  if (q.includes("disponibilidade") || q.includes("resumo")) {
    return {
      tool: `api.overview(range="24h")`,
      text: `Disponibilidade nas últimas 24 h: ${formatPercent(overview.availability.percent)} (meta ${formatPercent(overview.availability.slo_percent)}). ${servers.length} hosts monitorados: ${byStatus("ok").length} OK, ${byStatus("warning").length} em aviso, ${byStatus("critical").length} crítico(s) e ${byStatus("unknown").length} sem dados recentes. MTTR médio: ${formatDuration(overview.mttr_seconds)}.`,
    };
  }

  if (q.includes("relatório") || q.includes("relatorio")) {
    return {
      tool: "api.reports.create(type=\"incidents\", range=\"7d\")",
      text: "Para gerar o relatório, use a aba Relatórios (tipo Incidentes, últimos 7 dias). Na etapa 4 eu mesmo vou pedir a geração e redigir o texto.",
    };
  }

  if (q.includes("alerta") || q.includes("ativo")) {
    if (!alerts.length) return { tool: "api.alerts.list(status=\"active\")", text: "Não há alertas ativos no momento." };
    return {
      tool: "api.alerts.list(status=\"active\")",
      text: `${alerts.length} alerta(s) ativo(s): ` + alerts.slice(0, 6).map((a) => `${a.host_id} — ${a.trigger_name} (${formatMetric(a.metric, a.value_last)})`).join("; ") + (alerts.length > 6 ? "…" : "."),
    };
  }

  const critical = byStatus("critical"), warn = byStatus("warning");
  return {
    tool: "api.servers.list()",
    text: `No momento: ${critical.length} host(s) crítico(s)${critical.length ? ` (${critical.map((s) => s.id).join(", ")})` : ""} e ${warn.length} em aviso${warn.length ? ` (${warn.map((s) => s.id).join(", ")})` : ""}. Posso detalhar um servidor (cite o nome), listar alertas ativos ou resumir a disponibilidade. Respostas simuladas — a IA de verdade chega na etapa 4.`,
  };
}
