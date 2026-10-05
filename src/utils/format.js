import { METRIC_META } from "../config/metrics";

const nf1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

export function formatNumber(v, digits = 1) {
  if (v === null || v === undefined) return "—";
  return (digits === 2 ? nf2 : nf1).format(v);
}

// 96 -> "96%"; 79.4 (temp) -> "79,4°C"; reachable 1 -> "Online"
export function formatMetric(metric, value) {
  if (value === null || value === undefined) return "—";
  if (metric === "reachable") return value >= 1 ? "Online" : "Offline";
  return `${formatNumber(value)}${METRIC_META[metric]?.symbol ?? ""}`;
}

export function formatPercent(v) {
  return v === null || v === undefined ? "—" : `${formatNumber(v, 2)}%`;
}

// "há 45 s", "há 4 min", "há 2 h", "há 3 d"
export function formatRelative(iso, now = Date.now()) {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 10) return "agora";
  if (s < 60) return `há ${s} s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

// 75 -> "1 min 15 s"; 4140 -> "1 h 9 min"; 200000 -> "2 d 7 h"
export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ""}`;
  if (s < 86400) return `${Math.floor(s / 3600)} h${Math.floor((s % 3600) / 60) ? ` ${Math.floor((s % 3600) / 60)} min` : ""}`;
  return `${Math.floor(s / 86400)} d ${Math.floor((s % 86400) / 3600)} h`;
}

// 4082400 -> "47d 06h"
export function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const d = Math.floor(seconds / 86400);
  const h = String(Math.floor((seconds % 86400) / 3600)).padStart(2, "0");
  const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  return d > 0 ? `${d}d ${h}h` : `${h}h ${m}m`;
}

const dtf = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const timef = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const dayf = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" });

export function formatDateTime(iso) {
  return iso ? dtf.format(new Date(iso)) : "—";
}

// Rótulo do eixo X: hora para períodos curtos, dia/mês para longos
export function axisTimeFormatter(spanMs) {
  return (iso) => {
    const d = new Date(iso);
    return spanMs > 36 * 3600 * 1000 ? dayf.format(d) : timef.format(d);
  };
}

export function formatPeriod(fromIso, toIso) {
  return `${formatDateTime(fromIso)} – ${formatDateTime(toIso)}`;
}
