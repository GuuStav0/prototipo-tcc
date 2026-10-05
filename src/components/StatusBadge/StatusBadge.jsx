import { STATUS } from "../../data/mockData";
import Led from "../Led/Led";
import "./StatusBadge.css";

export default function StatusBadge({ status }) {
  const s = STATUS[status];
  return (
    <span className="smi-badge" style={{ color: s.color, borderColor: s.color + "55", background: s.color + "14" }}>
      <Led status={status} size={7} />
      {s.label}
    </span>
  );
}
