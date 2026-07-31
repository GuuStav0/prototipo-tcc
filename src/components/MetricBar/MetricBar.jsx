import React from "react";
import { STATUS, METRIC_META } from "../../data/mockData";
import "./MetricBar.css";

export default function MetricBar({ metric, value }) {
  const meta = METRIC_META[metric];
  const pct = metric === "temp" ? Math.min(100, (value / 90) * 100) : value;
  const tone = pct > 85 ? STATUS.critical.color : pct > 65 ? STATUS.warning.color : meta.color;
  return (
    <div className="smi-metricbar">
      <div className="smi-metricbar-head">
        <span><meta.icon size={12} strokeWidth={2.2} /> {meta.label}</span>
        <span className="smi-mono">{value}{meta.unit}</span>
      </div>
      <div className="smi-metricbar-track">
        <div className="smi-metricbar-fill" style={{ width: `${Math.min(100, pct)}%`, background: tone }} />
      </div>
    </div>
  );
}
