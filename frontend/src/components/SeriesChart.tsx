import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDay, formatMw, formatTime } from "../format";
import type { SeriesPoint } from "../types";
import { LegendItem, axisProps, gridProps, mwTick } from "./chartBits";
import { Status } from "./Status";

type Row = SeriesPoint & { t: number };

const HOUR = 3_600_000;
const withTime = (p: SeriesPoint): Row => ({ ...p, t: Date.parse(p.time) });

// Forecasts exist only on the hour. Draw the line through hourly slots alone, so the empty
// half-hours don't break it, while a genuinely missing hourly forecast stays a gap (null).
export function forecastLine(points: SeriesPoint[]): Row[] {
  return points.map(withTime).filter((r) => r.t % HOUR === 0);
}

function dayTicks(rows: Row[]): number[] {
  if (!rows.length) return [];
  const DAY = 86_400_000;
  const first = Math.ceil(rows[0].t / DAY) * DAY;
  const last = rows[rows.length - 1].t;
  const days = Math.floor((last - first) / DAY) + 1;
  const step = Math.max(1, Math.ceil(days / 10));
  const ticks = [];
  for (let t = first; t <= last; t += step * DAY) ticks.push(t);
  return ticks;
}

function SeriesTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="t-title">{formatTime(p.time)}</div>
      <div>Actual: {formatMw(p.actual_mw)}</div>
      <div>Forecast: {formatMw(p.forecast_mw)}</div>
      {p.error_mw != null && <div>Error: {p.error_mw > 0 ? "+" : ""}{formatMw(p.error_mw)}</div>}
      <div className="t-muted">
        {p.forecast_publish_time ? `Forecast published ${formatTime(p.forecast_publish_time)}` : "No hourly forecast for this half-hour"}
      </div>
    </div>
  );
}

export function SeriesChart({ points, height = 320 }: { points: SeriesPoint[]; height?: number }) {
  if (!points.length) return <Status kind="empty" />;
  const rows = points.map(withTime);
  const fcRows = forecastLine(points);
  return (
    <>
      <div className="legend">
        <LegendItem color="var(--series-actual)" label="Actual" />
        <LegendItem color="var(--series-forecast)" label="Forecast" dashed />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
            ticks={dayTicks(rows)} tickFormatter={(t: number) => formatDay(new Date(t).toISOString())} {...axisProps} />
          <YAxis tickFormatter={mwTick} width={56} {...axisProps} axisLine={false} />
          <Tooltip content={<SeriesTooltip />} cursor={{ stroke: "var(--text-muted)", strokeWidth: 1 }} />
          <Line dataKey="actual_mw" name="Actual" stroke="var(--series-actual)" strokeWidth={2}
            dot={false} activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }} isAnimationActive={false} />
          <Line data={fcRows} dataKey="forecast_mw" name="Forecast" stroke="var(--series-forecast)" strokeWidth={2}
            strokeDasharray="5 4" dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
