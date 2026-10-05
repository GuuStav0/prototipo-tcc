import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function BigChart({ data, color, unit }) {
  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
        <defs>
          <linearGradient id={`biggrad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.45} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#20293A" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="t" tick={{ fill: "#6B7690", fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={{ stroke: "#20293A" }} tickLine={false} interval={3} />
        <YAxis tick={{ fill: "#6B7690", fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} width={36} unit={unit} />
        <Tooltip
          contentStyle={{ background: "#111726", border: "1px solid #263144", borderRadius: 8, fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}
          labelStyle={{ color: "#8B94A7" }}
          itemStyle={{ color }}
        />
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#biggrad-${color.replace("#", "")})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
