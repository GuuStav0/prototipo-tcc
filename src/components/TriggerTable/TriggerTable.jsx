import React from "react";
import Led from "../Led/Led";

export default function TriggerTable({ rows, compact }) {
  return (
    <div className="smi-table-wrap">
      <table className="smi-table">
        <thead>
          <tr>
            <th></th>
            <th>Gatilho</th>
            {!compact && <th>Host</th>}
            <th>Condição</th>
            <th>Valor atual</th>
            <th>Último disparo</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td><Led status={t.severity} pulse={t.severity === "critical"} /></td>
              <td>{t.name}</td>
              {!compact && <td className="smi-mono smi-muted">{t.host}</td>}
              <td className="smi-mono smi-muted">{t.condition}</td>
              <td className="smi-mono">{t.value}</td>
              <td className="smi-mono smi-muted">{t.last}</td>
              <td><span className={"smi-pill " + (t.status === "Ativo" ? "smi-pill-active" : "smi-pill-resolved")}>{t.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
