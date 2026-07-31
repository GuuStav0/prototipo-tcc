import React from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

export default function MiniChart({ data, color }) {
  return (
    <ResponsiveContainer width="100%" height={46}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.5} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.6} fill={`url(#grad-${color.replace("#", "")})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
