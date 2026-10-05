import { STATUS } from "../../config/status";
import Led from "../Led/Led";
import "./StatusBadge.css";

export default function StatusBadge({ status, label }) {
  const s = STATUS[status] ?? STATUS.unknown;
  return (
    <span className="smi-badge" style={{ color: s.color, borderColor: s.color + "55", background: s.color + "14" }}>
      <Led status={status} size={7} />
      {label ?? s.label}
    </span>
  );
}
