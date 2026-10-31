import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatMw } from "../format";
import type { ByHorizonResponse } from "../types";
import { LegendItem, axisProps, gridProps, mwTick } from "./chartBits";
import { Status } from "./Status";

type Row = ByHorizonResponse["horizons"][number];

function HorizonTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="t-title">Published ≥ {p.horizon_h} h before delivery</div>
      <div>MAE: {formatMw(p.mae)}</div>
      <div>P90 shortfall: {formatMw(p.p90_shortfall)}</div>
      <div>Bias: {formatMw(p.bias)}</div>
    </div>
  );
}

export function HorizonChart({ data, selectedH }: { data: ByHorizonResponse; selectedH: number | null }) {
  if (!data.horizons.some((h) => h.n > 0)) return <Status kind="empty" />;
  return (
    <>
      <div className="legend">
        <LegendItem color="var(--series-actual)" label="MAE" />
        <LegendItem color="var(--series-forecast)" label="P90 shortfall" />
        <LegendItem color="var(--text-muted)" label="Day-ahead MAE" dashed />
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data.horizons} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="horizon_h" type="number" domain={[0, "dataMax"]} ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]}
            tickFormatter={(h: number) => `${h}h`} {...axisProps} />
          <YAxis tickFormatter={mwTick} width={56} {...axisProps} axisLine={false} />
          <Tooltip content={<HorizonTooltip />} cursor={{ stroke: "var(--text-muted)", strokeWidth: 1 }} />
          {data.day_ahead.mae != null && (
            <ReferenceLine y={data.day_ahead.mae} stroke="var(--text-muted)" strokeDasharray="4 4"
              label={{ value: "Day-ahead (09:20 cutoff)", position: "insideBottomLeft", fill: "var(--text-muted)", fontSize: 11 }} />
          )}
          {selectedH != null && <ReferenceLine x={selectedH} stroke="var(--text-secondary)" />}
          <Line dataKey="mae" stroke="var(--series-actual)" strokeWidth={2} dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }} isAnimationActive={false} />
          <Line dataKey="p90_shortfall" stroke="var(--series-forecast)" strokeWidth={2} dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}
