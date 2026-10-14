import { FlaskConical, Radio } from "lucide-react";
import "./ModeBadge.css";

// "Real" = dados de agente/SNMP; "Simulado" = dados do coletor simulado
export default function ModeBadge({ mode }) {
  const real = mode === "real";
  return (
    <span className={"smi-mode " + (real ? "smi-mode-real" : "smi-mode-sim")}
      title={real ? "Dados reais (agente ou SNMP)" : "Dados gerados pelo coletor simulado"}>
      {real ? <Radio size={11} /> : <FlaskConical size={11} />}
      {real ? "Real" : "Simulado"}
    </span>
  );
}
