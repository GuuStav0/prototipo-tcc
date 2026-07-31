import React, { useState } from "react";
import { Plus, Download } from "lucide-react";
import { REPORTS } from "../../data/mockData";

export default function Reports() {
  const [reports, setReports] = useState(REPORTS);
  const [showForm, setShowForm] = useState(false);
  const [type, setType] = useState("Disponibilidade");
  const [period, setPeriod] = useState("Últimos 7 dias");

  function handleGenerate(e) {
    e.preventDefault();
    setReports([
      { id: Date.now(), title: `Relatório de ${type}`, type, period, generatedAt: "agora", by: "Você" },
      ...reports,
    ]);
    setShowForm(false);
  }

  return (
    <div className="smi-stack">
      <div className="smi-card">
        <div className="smi-card-title-row">
          <div className="smi-card-title">Relatórios</div>
          <button className="smi-btn" onClick={() => setShowForm((v) => !v)}><Plus size={14} /> Gerar novo relatório</button>
        </div>
        {showForm && (
          <form className="smi-form" onSubmit={handleGenerate}>
            <div className="smi-form-row">
              <label>Tipo
                <select className="smi-select" value={type} onChange={(e) => setType(e.target.value)}>
                  <option>Disponibilidade</option>
                  <option>Incidentes</option>
                  <option>Desempenho</option>
                  <option>Auditoria</option>
                </select>
              </label>
              <label>Período
                <select className="smi-select" value={period} onChange={(e) => setPeriod(e.target.value)}>
                  <option>Últimas 24 horas</option>
                  <option>Últimos 7 dias</option>
                  <option>Últimos 30 dias</option>
                  <option>Personalizado</option>
                </select>
              </label>
            </div>
            <button type="submit" className="smi-btn">Confirmar geração</button>
          </form>
        )}
        <div className="smi-table-wrap">
          <table className="smi-table">
            <thead><tr><th>Relatório</th><th>Tipo</th><th>Período</th><th>Gerado em</th><th>Por</th><th></th></tr></thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td>{r.title}</td>
                  <td className="smi-muted">{r.type}</td>
                  <td className="smi-mono smi-muted">{r.period}</td>
                  <td className="smi-mono smi-muted">{r.generatedAt}</td>
                  <td className="smi-muted">{r.by}</td>
                  <td><button className="smi-icon-btn" title="Baixar (mock)"><Download size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
