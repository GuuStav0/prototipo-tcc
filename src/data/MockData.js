import { Cpu, MemoryStick, HardDrive, Thermometer } from "lucide-react";

export const STATUS = {
  ok: { label: "OK", color: "#34D399", glow: "rgba(52,211,153,0.55)" },
  warning: { label: "Aviso", color: "#FBBF24", glow: "rgba(251,191,36,0.55)" },
  critical: { label: "Crítico", color: "#F8717A", glow: "rgba(248,113,122,0.6)" },
};

export const METRIC_META = {
  cpu: { label: "CPU", unit: "%", icon: Cpu, color: "#7DD3FC" },
  ram: { label: "Memória", unit: "%", icon: MemoryStick, color: "#A78BFA" },
  disk: { label: "Disco", unit: "%", icon: HardDrive, color: "#FBBF24" },
  temp: { label: "Temperatura", unit: "°C", icon: Thermometer, color: "#F8717A" },
};

export const SERVERS = [
  { id: "srv-web-01", name: "srv-web-01", role: "Web / Nginx", os: "Ubuntu 22.04", ip: "10.0.4.11", status: "ok", cpu: 34, ram: 52, disk: 61, temp: 46, uptime: "47d 06h" },
  { id: "srv-web-02", name: "srv-web-02", role: "Web / Nginx", os: "Ubuntu 22.04", ip: "10.0.4.12", status: "ok", cpu: 29, ram: 48, disk: 58, temp: 44, uptime: "47d 06h" },
  { id: "srv-db-01", name: "srv-db-01", role: "Banco / PostgreSQL", os: "Debian 12", ip: "10.0.2.21", status: "warning", cpu: 78, ram: 84, disk: 71, temp: 58, uptime: "112d 03h" },
  { id: "srv-db-02", name: "srv-db-02", role: "Banco / MySQL", os: "Debian 12", ip: "10.0.2.22", status: "ok", cpu: 41, ram: 63, disk: 55, temp: 49, uptime: "88d 14h" },
  { id: "srv-app-01", name: "srv-app-01", role: "API Gateway", os: "Ubuntu 22.04", ip: "10.0.3.31", status: "ok", cpu: 37, ram: 55, disk: 40, temp: 45, uptime: "30d 02h" },
  { id: "srv-app-02", name: "srv-app-02", role: "API Gateway", os: "Ubuntu 22.04", ip: "10.0.3.32", status: "critical", cpu: 96, ram: 91, disk: 88, temp: 79, uptime: "5d 20h" },
  { id: "srv-cache-01", name: "srv-cache-01", role: "Cache / Redis", os: "Alpine 3.19", ip: "10.0.5.41", status: "ok", cpu: 22, ram: 38, disk: 25, temp: 41, uptime: "60d 01h" },
  { id: "srv-backup-01", name: "srv-backup-01", role: "Backup / Bacula", os: "CentOS 9", ip: "10.0.6.51", status: "warning", cpu: 65, ram: 72, disk: 93, temp: 55, uptime: "200d 08h" },
  { id: "srv-mail-01", name: "srv-mail-01", role: "E-mail / Postfix", os: "Debian 12", ip: "10.0.7.61", status: "ok", cpu: 30, ram: 44, disk: 62, temp: 43, uptime: "150d 11h" },
  { id: "srv-monitor-01", name: "srv-monitor-01", role: "Coletor SNMP", os: "Ubuntu 22.04", ip: "10.0.1.10", status: "ok", cpu: 26, ram: 40, disk: 35, temp: 42, uptime: "300d 00h" },
];

export const TRIGGERS = [
  { id: 1, name: "CPU acima do limite", host: "srv-app-02", condition: "CPU > 90% por 5 min", value: "96%", severity: "critical", last: "há 4 min", status: "Ativo" },
  { id: 2, name: "Temperatura elevada", host: "srv-app-02", condition: "Temperatura > 75°C", value: "79°C", severity: "critical", last: "há 6 min", status: "Ativo" },
  { id: 3, name: "Uso de disco elevado", host: "srv-backup-01", condition: "Disco > 90%", value: "93%", severity: "warning", last: "há 22 min", status: "Ativo" },
  { id: 4, name: "Uso de memória elevado", host: "srv-db-01", condition: "RAM > 80%", value: "84%", severity: "warning", last: "há 41 min", status: "Ativo" },
  { id: 5, name: "Uso de CPU elevado", host: "srv-db-01", condition: "CPU > 85% por 5 min", value: "78%", severity: "ok", last: "há 1h", status: "Resolvido" },
  { id: 6, name: "Latência de I/O", host: "srv-db-01", condition: "I/O wait > 15%", value: "12%", severity: "ok", last: "há 2h", status: "Resolvido" },
  { id: 7, name: "Serviço SSH indisponível", host: "srv-mail-01", condition: "Porta 22 sem resposta", value: "Disponível", severity: "ok", last: "há 5d", status: "Resolvido" },
  { id: 8, name: "Job de backup falhou", host: "srv-backup-01", condition: "Job de backup ≠ sucesso", value: "Sucesso", severity: "ok", last: "há 3d", status: "Resolvido" },
];

export const REPORTS = [
  { id: 1, title: "Disponibilidade Semanal", type: "Disponibilidade", period: "21–27 jul 2026", generatedAt: "28 jul 2026, 08:12", by: "Automático" },
  { id: 2, title: "Resumo de Incidentes", type: "Incidentes", period: "julho 2026", generatedAt: "25 jul 2026, 17:40", by: "Luiz Gustavo" },
  { id: 3, title: "Desempenho de Hardware", type: "Desempenho", period: "01–15 jul 2026", generatedAt: "16 jul 2026, 09:05", by: "Automático" },
  { id: 4, title: "Comparativo com Zabbix", type: "Auditoria", period: "2º trimestre 2026", generatedAt: "02 jul 2026, 12:00", by: "Paulo Eduardo" },
];

function genSeries(base, volatility, len = 24, trend = 0) {
  const arr = [];
  let val = base;
  for (let i = 0; i < len; i++) {
    val += (Math.random() - 0.5) * volatility + trend;
    val = Math.max(3, Math.min(99, val));
    arr.push({ t: `${String(i).padStart(2, "0")}h`, v: Math.round(val * 10) / 10 });
  }
  return arr;
}

const SERIES_CACHE = {};
export function seriesFor(hostId, metric) {
  const key = hostId + "-" + metric;
  if (!SERIES_CACHE[key]) {
    const host = SERVERS.find((s) => s.id === hostId);
    const base = host ? host[metric] : 40;
    const trend = host && host.status === "critical" ? 0.6 : host && host.status === "warning" ? 0.15 : 0;
    SERIES_CACHE[key] = genSeries(Math.max(10, base - 18), 10, 24, trend);
  }
  return SERIES_CACHE[key];
}
