// Rótulos e cores dos estados do contrato (ok, warning, critical, unknown).
export const STATUS = {
  ok: { label: "OK", color: "#34D399", glow: "rgba(52,211,153,0.55)" },
  warning: { label: "Aviso", color: "#FBBF24", glow: "rgba(251,191,36,0.55)" },
  critical: { label: "Crítico", color: "#F8717A", glow: "rgba(248,113,122,0.6)" },
  unknown: { label: "Sem dados", color: "#6B7690", glow: "rgba(107,118,144,0.35)" },
};

export const STATUS_ORDER = ["critical", "warning", "ok", "unknown"];

export const ALERT_STATUS = {
  active: "Ativo",
  resolved: "Resolvido",
};

export const VALIDATION = {
  true_positive: "Verdadeiro",
  false_positive: "Falso positivo",
};

export const REPORT_TYPES = {
  availability: "Disponibilidade",
  incidents: "Incidentes",
  performance: "Desempenho",
  audit: "Auditoria",
};

export const REPORT_STATUS = {
  pending: "Gerando…",
  ready: "Pronto",
  failed: "Falhou",
};

export const REPORT_AUTHOR = {
  system: "Automático",
  user: "Usuário",
  assistant: "Assistente IA",
};
