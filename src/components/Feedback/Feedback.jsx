import { AlertCircle, Loader2, RefreshCw, WifiOff } from "lucide-react";
import "./Feedback.css";

export function Loading({ label = "Carregando…" }) {
  return (
    <div className="smi-feedback">
      <Loader2 size={15} className="smi-spin" /> {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  const offline = error.code === "network_error";
  return (
    <div className="smi-feedback smi-feedback-error">
      {offline ? <WifiOff size={15} /> : <AlertCircle size={15} />}
      <span>{error.message}</span>
      {onRetry && (
        <button className="smi-link" onClick={onRetry}>
          <RefreshCw size={12} /> Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="smi-feedback">{children}</div>;
}

// Aviso no topo quando a API está fora do ar
export function ApiOfflineBanner({ error }) {
  if (error?.code !== "network_error") return null;
  return (
    <div className="smi-offline">
      <WifiOff size={15} />
      <div>
        <b>API do SMI indisponível.</b> Inicie o backend (instruções em <span className="smi-mono">backend/README.md</span>).
        Nova tentativa a cada 10 s.
      </div>
    </div>
  );
}
