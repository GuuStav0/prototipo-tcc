import { useState } from "react";
import { TRIGGERS, STATUS } from "../../data/mockData";
import TriggerTable from "../../components/TriggerTable/TriggerTable";

export default function Triggers() {
  const [filter, setFilter] = useState("all");
  const rows = filter === "all" ? TRIGGERS : TRIGGERS.filter((t) => t.severity === filter);

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title">Motor de gatilhos</div>
        <p className="smi-muted" style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 720 }}>
          Cada gatilho compara uma métrica coletada (CPU, memória, disco, temperatura ou disponibilidade de serviço)
          a um limiar configurado, classificando o host em três estados: <b style={{ color: STATUS.ok.color }}>OK</b>,{" "}
          <b style={{ color: STATUS.warning.color }}>Aviso</b> ou <b style={{ color: STATUS.critical.color }}>Crítico</b>.
        </p>
        <div className="smi-chipfilter">
          {["all", "critical", "warning", "ok"].map((f) => (
            <button key={f} className={"smi-chip" + (filter === f ? " smi-chip-active" : "")} onClick={() => setFilter(f)}>
              {f === "all" ? "Todos" : STATUS[f].label}
            </button>
          ))}
        </div>
      </div>
      <div className="smi-card">
        <TriggerTable rows={rows} />
      </div>
    </div>
  );
}
