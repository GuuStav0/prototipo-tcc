import { Link } from "react-router-dom";
import { Gauge, Server, AlertTriangle, Clock, ChevronRight } from "lucide-react";
import { SERVERS, TRIGGERS, STATUS, METRIC_META, seriesFor } from "../../data/mockData";
import KpiCard from "../../components/KpiCard/KpiCard";
import Led from "../../components/Led/Led";
import MiniChart from "../../components/charts/MiniChart";

export default function Dashboard() {
  const okCount = SERVERS.filter((s) => s.status === "ok").length;
  const activeTriggers = TRIGGERS.filter((t) => t.status === "Ativo");
  const critCount = activeTriggers.filter((t) => t.severity === "critical").length;
  const warnCount = activeTriggers.filter((t) => t.severity === "warning").length;
  const total = TRIGGERS.length;

  return (
    <div className="smi-stack">
      <div className="smi-grid-kpi">
        <KpiCard icon={Gauge} label="Disponibilidade geral" value="99,94%" sub="meta SRE: 99,9%" tone="#34D399" />
        <KpiCard icon={Server} label="Hosts saudáveis" value={`${okCount}/${SERVERS.length}`} sub="verificados via SNMP" tone="#7DD3FC" />
        <KpiCard icon={AlertTriangle} label="Alertas ativos" value={activeTriggers.length} sub={`${critCount} crítico · ${warnCount} aviso`} tone="#F8717A" />
        <KpiCard icon={Clock} label="MTTR médio" value="18 min" sub="últimos 30 dias" tone="#A78BFA" />
      </div>

      <div className="smi-grid-2">
        <div className="smi-card">
          <div className="smi-card-title">Gatilhos por severidade</div>
          <div className="smi-severity-bar">
            <div style={{ width: `${(critCount / total) * 100}%`, background: STATUS.critical.color }} />
            <div style={{ width: `${(warnCount / total) * 100}%`, background: STATUS.warning.color }} />
            <div style={{ width: `${((total - critCount - warnCount) / total) * 100}%`, background: STATUS.ok.color }} />
          </div>
          <div className="smi-legend">
            <span><Led status="critical" /> Crítico · {critCount}</span>
            <span><Led status="warning" /> Aviso · {warnCount}</span>
            <span><Led status="ok" /> OK · {total - critCount - warnCount}</span>
          </div>
        </div>

        <div className="smi-card">
          <div className="smi-card-title">Últimos disparos</div>
          <div className="smi-alertlist">
            {TRIGGERS.slice(0, 5).map((t) => (
              <div className="smi-alertrow" key={t.id}>
                <Led status={t.severity} pulse />
                <div className="smi-alertrow-body">
                  <span className="smi-alertrow-name">{t.name}</span>
                  <span className="smi-muted smi-mono">{t.host} · {t.condition}</span>
                </div>
                <span className="smi-muted smi-mono">{t.last}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="smi-card">
        <div className="smi-card-title-row">
          <div className="smi-card-title">Servidores monitorados</div>
          <Link className="smi-link" to="/servidores">Ver todos <ChevronRight size={14} /></Link>
        </div>
        <div className="smi-servergrid-mini">
          {SERVERS.map((s) => (
            <Link key={s.id} className="smi-minicard" to={`/servidores/${s.id}`}>
              <div className="smi-minicard-head">
                <Led status={s.status} pulse />
                <span className="smi-mono">{s.name}</span>
              </div>
              <span className="smi-muted smi-minicard-role">{s.role}</span>
              <MiniChart data={seriesFor(s.id, "cpu")} color={s.status === "critical" ? STATUS.critical.color : METRIC_META.cpu.color} />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
