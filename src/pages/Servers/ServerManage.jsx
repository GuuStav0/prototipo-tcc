import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Power, Repeat, Trash2 } from "lucide-react";
import { api } from "../../api/client";
import { formatRelative } from "../../utils/format";
import ModeBadge from "../../components/ModeBadge/ModeBadge";

function method(host) {
  const c = host.collection;
  if (host.mode === "simulated") return "Coletor simulado";
  const parts = [];
  if (c.agent.enabled) parts.push("Agente (o servidor envia)");
  if (c.snmp.enabled) parts.push(`SNMP ${c.snmp.version} (o SMI consulta ${host.address}:${c.snmp.port})`);
  return parts.join(" + ") || "Nenhuma forma de coleta ativa";
}

// Coleta, modo simulado/real, ativar/desativar e remoção do servidor
export default function ServerManage({ host, isNew, onChanged }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [showSetup, setShowSetup] = useState(isNew || (host.mode === "real" && !host.last_seen_at));

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleMode() {
    const to = host.mode === "real" ? "simulated" : "real";
    const msg = to === "simulated"
      ? `Passar ${host.id} para SIMULADO? A partir de agora ele só aceita dados do coletor simulado; o agente/SNMP deste servidor será recusado.`
      : `Passar ${host.id} para REAL? A partir de agora ele só aceita dados do agente ou SNMP; o simulador deixa de gerar dados para ele.`;
    if (window.confirm(msg)) run(() => api.updateServer(host.id, { mode: to }));
  }

  function remove() {
    if (!window.confirm(`Remover ${host.id} do monitoramento? As métricas dele serão apagadas; os alertas antigos ficam no histórico.`)) return;
    run(async () => {
      await api.deleteServer(host.id);
      navigate("/servidores");
    });
  }

  const agent = host.mode === "real" && host.collection.agent.enabled;

  return (
    <div className="smi-card">
      <div className="smi-card-title-row">
        <div className="smi-card-title" style={{ margin: 0 }}>Coleta e gerenciamento</div>
        <ModeBadge mode={host.mode} />
      </div>
      <div className="smi-manage-grid">
        <div><span className="smi-muted">Forma de coleta</span><div>{method(host)}</div></div>
        <div><span className="smi-muted">Monitoramento</span><div>{host.enabled ? "Ativo" : "Desativado"}</div></div>
        <div><span className="smi-muted">Última coleta</span><div>{formatRelative(host.last_seen_at)}</div></div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <button className="smi-btn" disabled={busy} onClick={toggleMode}>
          <Repeat size={14} /> {host.mode === "real" ? "Passar para simulado" : "Passar para real"}
        </button>
        <button className="smi-btn" disabled={busy} onClick={() => run(() => api.updateServer(host.id, { enabled: !host.enabled }))}>
          <Power size={14} /> {host.enabled ? "Desativar monitoramento" : "Ativar monitoramento"}
        </button>
        <button className="smi-btn" disabled={busy} onClick={remove}><Trash2 size={14} /> Remover</button>
        {agent && (
          <button className="smi-link" style={{ marginLeft: "auto" }} onClick={() => setShowSetup((v) => !v)}>
            {showSetup ? "Ocultar instalação do agente" : "Como instalar o agente"}
          </button>
        )}
      </div>
      {error && <div className="smi-feedback smi-feedback-error">{error}</div>}

      {agent && showSetup && (
        <div className="smi-setup">
          <div style={{ marginBottom: 6 }}>
            {isNew && <b>Servidor cadastrado. </b>}
            Instale o agente no servidor (passo a passo em <span className="smi-mono">docs/vps/GUIA-VPS.md</span>) e use
            esta configuração em <span className="smi-mono">/etc/smi-agent/agent.env</span>:
          </div>
          <pre className="smi-code">{`SMI_API_URL=http://<IP do PC no Tailscale>:8000/api/v1
SMI_INGEST_TOKEN=<o mesmo SMI_INGEST_TOKEN do backend/.env>
SMI_HOST_ID=${host.id}
SMI_INTERVAL=15`}</pre>
          <div className="smi-muted">
            Quando o agente começar a enviar, este servidor sai de "Sem dados". Se ele parar de enviar por mais de 30 s,
            o SMI registra o servidor como inalcançável e o alerta crítico dispara.
          </div>
        </div>
      )}
    </div>
  );
}
