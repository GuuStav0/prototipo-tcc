import { STATUS } from "../../config/status";
import "./Led.css";

export default function Led({ status, size = 9, pulse = false }) {
  const s = STATUS[status] ?? STATUS.unknown;
  return (
    <span
      className={"smi-led" + (pulse && status === "critical" ? " smi-led-pulse" : "")}
      style={{ width: size, height: size, background: s.color, boxShadow: `0 0 8px ${s.glow}` }}
      title={s.label}
    />
  );
}
