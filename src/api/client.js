// Cliente da API do SMI (docs/contrato/openapi.yaml).
// Em desenvolvimento o Vite repassa /api para o backend (ver vite.config.js).
const BASE = (import.meta.env.VITE_API_URL ?? "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(path, { method = "GET", params, body, signal } = {}) {
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") query.append(k, v);
  }
  const url = `${BASE}${path}${query.size ? `?${query}` : ""}`;

  let res;
  try {
    res = await fetch(url, {
      method,
      signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Não foi possível conectar à API do SMI.");
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // o proxy do Vite responde 500/502 sem corpo JSON quando o backend está desligado
    if (!data?.error && res.status >= 500) {
      throw new ApiError(0, "network_error", "Não foi possível conectar à API do SMI.");
    }
    throw new ApiError(res.status, data?.error?.code ?? `http_${res.status}`, data?.error?.message ?? res.statusText);
  }
  return data;
}

export const api = {
  health: (opts) => request("/health", opts),
  overview: (range = "24h", opts) => request("/overview", { params: { range }, ...opts }),

  servers: (params, opts) => request("/servers", { params, ...opts }),
  server: (id, opts) => request(`/servers/${encodeURIComponent(id)}`, opts),
  createServer: (body) => request("/servers", { method: "POST", body }),
  updateServer: (id, body) => request(`/servers/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  deleteServer: (id) => request(`/servers/${encodeURIComponent(id)}`, { method: "DELETE" }),
  // metric: "cpu" ou "cpu,ram,disk,temp"
  metrics: (id, params, opts) => request(`/servers/${encodeURIComponent(id)}/metrics`, { params, ...opts }),

  triggers: (params, opts) => request("/triggers", { params, ...opts }),
  createTrigger: (body) => request("/triggers", { method: "POST", body }),
  updateTrigger: (id, body) => request(`/triggers/${id}`, { method: "PATCH", body }),
  deleteTrigger: (id) => request(`/triggers/${id}`, { method: "DELETE" }),

  alerts: (params, opts) => request("/alerts", { params, ...opts }),
  updateAlert: (id, body) => request(`/alerts/${id}`, { method: "PATCH", body }),

  assistantStatus: (opts) => request("/assistant/status", opts),
  assistantMessage: (body, opts) => request("/assistant/messages", { method: "POST", body, ...opts }),

  reports: (opts) => request("/reports", opts),
  report: (id, opts) => request(`/reports/${id}`, opts),
  createReport: (body) => request("/reports", { method: "POST", body }),
};
