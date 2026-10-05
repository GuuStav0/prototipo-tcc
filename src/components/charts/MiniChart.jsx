import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toChartData } from "./series";

// data = pontos da API: [{ t, v }]
export default function MiniChart({ data, color, max = 100 }) {
  const gradId = `grad-${color.replace("#", "")}`;
  return (
    <ResponsiveContainer width="100%" height={46}>
      <AreaChart data={toChartData(data)} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.5} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis hide dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} />
        <YAxis hide domain={[0, max]} />
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.6} fill={`url(#${gradId})`} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
