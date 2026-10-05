import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { STATUS } from "../../config/status";
import { axisTimeFormatter, formatDateTime, formatNumber } from "../../utils/format";
import { AXIS_TICK, TOOLTIP_STYLE, toChartData } from "./series";

// data = pontos da API: [{ t: ISO, v: número | null }]
// thresholds = { warning, critical } da regra de gatilho, desenhados como linhas tracejadas
export default function BigChart({ data, color, unit, thresholds, height = 230 }) {
  const points = toChartData(data);
  const span = points.length > 1 ? points.at(-1).ts - points[0].ts : 0;
  const gradId = `biggrad-${color.replace("#", "")}`;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={points} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.45} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#20293A" strokeDasharray="3 5" vertical={false} />
        <XAxis
          dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={AXIS_TICK} tickFormatter={axisTimeFormatter(span)} axisLine={{ stroke: "#20293A" }} tickLine={false} minTickGap={40}
        />
        <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={50} unit={unit} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelStyle={{ color: "#8B94A7" }}
          itemStyle={{ color }}
          labelFormatter={formatDateTime}
          formatter={(v) => [v === null ? "sem dados" : `${formatNumber(v)}${unit}`, "valor"]}
        />
        {thresholds?.warning != null && (
          <ReferenceLine y={thresholds.warning} stroke={STATUS.warning.color} strokeDasharray="4 4" strokeOpacity={0.7} ifOverflow="extendDomain" />
        )}
        {thresholds?.critical != null && (
          <ReferenceLine y={thresholds.critical} stroke={STATUS.critical.color} strokeDasharray="4 4" strokeOpacity={0.7} ifOverflow="extendDomain" />
        )}
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#${gradId})`} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
