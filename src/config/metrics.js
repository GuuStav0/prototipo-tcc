import { Cpu, MemoryStick, HardDrive, Thermometer, Wifi } from "lucide-react";

// Métricas do contrato. "symbol" é como a unidade aparece na tela.
export const METRIC_META = {
  cpu: { label: "CPU", symbol: "%", icon: Cpu, color: "#7DD3FC", max: 100 },
  ram: { label: "Memória", symbol: "%", icon: MemoryStick, color: "#A78BFA", max: 100 },
  disk: { label: "Disco", symbol: "%", icon: HardDrive, color: "#FBBF24", max: 100 },
  temp: { label: "Temperatura", symbol: "°C", icon: Thermometer, color: "#F8717A", max: 90 },
  reachable: { label: "Alcance", symbol: "", icon: Wifi, color: "#34D399", max: 1 },
};

// Métricas com gráfico e barra (reachable é sim/não)
export const CHART_METRICS = ["cpu", "ram", "disk", "temp"];

export const OPERATORS = {
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
};

export const RANGES = [
  { id: "1h", label: "1 h" },
  { id: "6h", label: "6 h" },
  { id: "24h", label: "24 h" },
  { id: "7d", label: "7 dias" },
];

// Meta do TCC 4.5: alerta no dashboard em até 90 s.
// Pior caso = coleta (15 s) + duração do gatilho + atualização da tela (10 s).
export const DETECTION_TARGET_SECONDS = 90;
export const POLL_SECONDS = 15;
export const REFRESH_SECONDS = 10;
export function worstCaseDetection(durationSeconds) {
  return POLL_SECONDS + durationSeconds + REFRESH_SECONDS;
}
