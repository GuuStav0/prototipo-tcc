import { useState } from "react";
import { api } from "../../api/client";

const EMPTY = {
  id: "", role: "", os: "", address: "", location: "",
  method: "agent",
  snmp_version: "v3", snmp_port: 161, snmp_community: "", snmp_username: "", snmp_auth_password: "", snmp_priv_password: "",
};

// Cadastro de servidor real. O id vira o SMI_HOST_ID do agente.
export default function ServerForm({ onCreated, onCancel }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const snmp = form.method === "snmp";

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const id = form.id.trim().toLowerCase();
    const body = {
      id, name: id, address: form.address.trim(), role: form.role.trim(), os: form.os.trim(),
      location: form.location.trim() || null,
      mode: "real",
      agent: { enabled: !snmp },
      snmp: snmp
        ? {
            enabled: true, version: form.snmp_version, port: Number(form.snmp_port),
            ...(form.snmp_version === "v2c"
              ? { community: form.snmp_community }
              : { username: form.snmp_username, auth_password: form.snmp_auth_password, priv_password: form.snmp_priv_password }),
          }
        : { enabled: false },
    };
    try {
      onCreated(await api.createServer(body));
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <form className="smi-form" onSubmit={submit}>
      <div className="smi-card-title" style={{ margin: 0 }}>Cadastrar servidor real</div>
      <div className="smi-form-row">
        <label>Identificador
          <input className="smi-select" required pattern="[a-z0-9][a-z0-9\-]{1,62}" value={form.id} onChange={set("id")}
            placeholder="vps-hostinger" title="letras minúsculas, números e hífen" />
        </label>
        <label>Função
          <input className="smi-select" value={form.role} onChange={set("role")} placeholder="Web / Laravel" />
        </label>
        <label>Sistema
          <input className="smi-select" value={form.os} onChange={set("os")} placeholder="Ubuntu 24.04" />
        </label>
      </div>
      <div className="smi-form-row">
        <label>Endereço na rede Tailscale
          <input className="smi-select" required value={form.address} onChange={set("address")} placeholder="100.x.y.z" />
        </label>
        <label>Local (opcional)
          <input className="smi-select" value={form.location} onChange={set("location")} placeholder="Hostinger KVM 2" />
        </label>
        <label>Forma de coleta
          <select className="smi-select" value={form.method} onChange={set("method")}>
            <option value="agent">Agente (o servidor envia os dados)</option>
            <option value="snmp">SNMP (o SMI consulta o servidor)</option>
          </select>
        </label>
      </div>

      {snmp && (
        <div className="smi-form-row">
          <label>Versão
            <select className="smi-select" value={form.snmp_version} onChange={set("snmp_version")}>
              <option value="v3">v3 (recomendado: autenticado e criptografado)</option>
              <option value="v2c">v2c (senha em texto puro)</option>
            </select>
          </label>
          {form.snmp_version === "v2c" ? (
            <label>Community
              <input className="smi-select" required value={form.snmp_community} onChange={set("snmp_community")} />
            </label>
          ) : (
            <>
              <label>Usuário
                <input className="smi-select" required value={form.snmp_username} onChange={set("snmp_username")} placeholder="smi" />
              </label>
              <label>Senha de autenticação (SHA)
                <input className="smi-select" type="password" required minLength={8} value={form.snmp_auth_password} onChange={set("snmp_auth_password")} />
              </label>
              <label>Senha de criptografia (AES)
                <input className="smi-select" type="password" required minLength={8} value={form.snmp_priv_password} onChange={set("snmp_priv_password")} />
              </label>
            </>
          )}
        </div>
      )}

      <div className="smi-muted" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
        {snmp
          ? "O coletor SNMP (backend/collector/snmp_poller.py) vai consultar este endereço a cada 15 s. As senhas ficam só no backend e nunca voltam pela API."
          : "Depois de cadastrar, instale o agente no servidor usando este identificador como SMI_HOST_ID (passo a passo em docs/vps/GUIA-VPS.md)."}
      </div>
      {error && <div className="smi-feedback smi-feedback-error" style={{ padding: 0 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="smi-btn" disabled={saving}>{saving ? "Salvando…" : "Cadastrar"}</button>
        <button type="button" className="smi-btn" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}
