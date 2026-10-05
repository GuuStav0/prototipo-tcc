import { METRIC_META, OPERATORS } from "../config/metrics";
import { formatNumber } from "./format";

// Mesma regra do backend: regras específicas do host substituem as globais da mesma métrica
export function rulesFor(rules, hostId) {
  const enabled = rules.filter((r) => r.enabled);
  const specific = new Set(enabled.filter((r) => r.host_id === hostId).map((r) => r.metric));
  return enabled.filter((r) => r.host_id === hostId || !specific.has(r.metric));
}

// "CPU: aviso > 80% · crítico > 90%"
export function describeRule(r, { withMetric = true } = {}) {
  const meta = METRIC_META[r.metric];
  const op = OPERATORS[r.operator];
  const parts = [];
  if (r.warning_threshold !== null) parts.push(`aviso ${op} ${formatNumber(r.warning_threshold)}${meta.symbol}`);
  if (r.critical_threshold !== null) parts.push(`crítico ${op} ${formatNumber(r.critical_threshold)}${meta.symbol}`);
  return (withMetric ? `${meta.label}: ` : "") + parts.join(" · ");
}
