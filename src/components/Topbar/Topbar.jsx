import React from "react";
import { useLocation } from "react-router-dom";
import { Search, Bell, Sparkles } from "lucide-react";
import { NAV } from "../../config/navigation";
import { TRIGGERS } from "../../data/mockData";
import "./Topbar.css";

export default function Topbar({ chatOpen, onToggleChat }) {
  const location = useLocation();
  const current = NAV.find((n) => location.pathname.startsWith(n.path));
  const activeAlerts = TRIGGERS.filter((t) => t.status === "Ativo").length;

  return (
    <header className="smi-topbar">
      <div>
        <div className="smi-topbar-crumb smi-muted smi-mono">Painel / {current?.label ?? ""}</div>
        <div className="smi-topbar-title">{current?.label ?? ""}</div>
      </div>
      <div className="smi-topbar-actions">
        <button className="smi-icon-btn"><Search size={16} /></button>
        <button className="smi-icon-btn" style={{ position: "relative" }}>
          <Bell size={16} />
          {activeAlerts > 0 && <span className="smi-bellbadge">{activeAlerts}</span>}
        </button>
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
