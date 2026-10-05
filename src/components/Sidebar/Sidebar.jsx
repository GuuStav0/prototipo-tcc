import { NavLink } from "react-router-dom";
import { Activity } from "lucide-react";
import { NAV } from "../../config/navigation";
import { useLive } from "../../context/live";
import "./Sidebar.css";

export default function Sidebar() {
  const { overview } = useLive();
  const activeAlerts = overview ? overview.alerts_active.warning + overview.alerts_active.critical : 0;

  return (
    <nav className="smi-sidebar">
      <div className="smi-brand">
        <div className="smi-brand-mark"><Activity size={16} strokeWidth={2.4} /></div>
        <div>
          <div className="smi-brand-title">SMI</div>
          <div className="smi-brand-sub">Integridade de Servidores</div>
        </div>
      </div>

      <div className="smi-nav">
        {NAV.map((n) => (
          <NavLink
            key={n.id}
            to={n.path}
            className={({ isActive }) => "smi-navitem" + (isActive ? " smi-navitem-active" : "")}
          >
            <n.icon size={16} strokeWidth={2} />
            <span>{n.label}</span>
            {n.id === "triggers" && activeAlerts > 0 && <span className="smi-navbadge">{activeAlerts}</span>}
          </NavLink>
        ))}
      </div>

      <div className="smi-sidebar-foot">
        <div className="smi-pulseline">
          <svg viewBox="0 0 200 40" width="100%" height="34">
            <polyline
              points="0,20 20,20 28,6 36,34 44,20 60,20 68,12 76,28 84,20 200,20"
              fill="none"
              stroke="#34D399"
              strokeWidth="1.6"
              className="smi-pulseline-path"
            />
          </svg>
        </div>
        <div className="smi-muted smi-mono" style={{ fontSize: 10.5 }}>SMI v1.0 · SNMP / IPMI · MCP</div>
      </div>
    </nav>
  );
}
