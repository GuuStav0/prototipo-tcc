import { Link, useLocation } from "react-router-dom";
import { Bell, Sparkles } from "lucide-react";
import { NAV } from "../../config/navigation";
import { useLive } from "../../context/live";
import { formatRelative } from "../../utils/format";
import "./Topbar.css";

export default function Topbar({ chatOpen, onToggleChat }) {
  const location = useLocation();
  const current = NAV.find((n) => location.pathname.startsWith(n.path));
  const { overview } = useLive();
  const activeAlerts = overview ? overview.alerts_active.warning + overview.alerts_active.critical : 0;

  return (
    <header className="smi-topbar">
      <div>
        <div className="smi-topbar-crumb smi-muted smi-mono">Painel / {current?.label ?? ""}</div>
        <div className="smi-topbar-title">{current?.label ?? ""}</div>
      </div>
      <div className="smi-topbar-actions">
        {overview && (
          <span className="smi-muted smi-mono smi-topbar-updated" title="Dados atualizados automaticamente a cada 10 s">
            atualizado {formatRelative(overview.generated_at)}
          </span>
        )}
        <Link to="/gatilhos" className="smi-icon-btn" style={{ position: "relative" }} title="Alertas ativos">
          <Bell size={16} />
          {activeAlerts > 0 && <span className="smi-bellbadge">{activeAlerts > 9 ? "9+" : activeAlerts}</span>}
        </Link>
        <button
          className={"smi-btn smi-btn-ai" + (chatOpen ? " smi-btn-ai-active" : "")}
          onClick={onToggleChat}
        >
          <Sparkles size={15} /> Assistente MCP
        </button>
      </div>
    </header>
  );
}
