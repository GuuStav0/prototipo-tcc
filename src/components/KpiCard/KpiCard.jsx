import React from "react";
import "./KpiCard.css";

export default function KpiCard({ icon: Icon, label, value, sub, tone }) {
  return (
    <div className="smi-card smi-kpi">
      <div className="smi-kpi-icon" style={{ color: tone }}><Icon size={18} strokeWidth={2} /></div>
      <div className="smi-kpi-value">{value}</div>
      <div className="smi-kpi-label">{label}</div>
      {sub && <div className="smi-kpi-sub">{sub}</div>}
    </div>
  );
}
