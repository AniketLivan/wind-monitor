import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Bin } from "../types";
import { LegendItem, axisProps, gridProps, mwTick } from "./chartBits";
import { Status } from "./Status";

function BinTooltip({ active, payload }: { active?: boolean; payload?: { payload: Bin }[] }) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  const kind = b.lo_mw >= 0 ? "over-forecast" : "under-forecast";
  return (
    <div className="tooltip">
      <div className="t-title">{b.lo_mw.toLocaleString("en-GB")} to {b.hi_mw.toLocaleString("en-GB")} MW</div>
      <div>{b.count} slots ({kind})</div>
    </div>
  );
}

export function ErrorHistogram({ bins }: { bins: Bin[] }) {
  if (!bins.length) return <Status kind="empty" />;
  return (
    <>
      <div className="legend">
        <LegendItem color="var(--over)" label="Over-forecast (wind fell short)" />
        <LegendItem color="var(--under)" label="Under-forecast" />
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barCategoryGap={2}>
          <CartesianGrid {...gridProps} />
          {/* Each bar is labelled with its lower edge; the tooltip gives the full range. */}
          <XAxis dataKey="lo_mw" tickFormatter={(v: number) => mwTick(v)} {...axisProps} />
          <YAxis allowDecimals={false} width={40} {...axisProps} axisLine={false} />
          <Tooltip content={<BinTooltip />} cursor={{ fill: "var(--grid)" }} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {bins.map((b) => (
              <Cell key={b.lo_mw} fill={b.lo_mw >= 0 ? "var(--over)" : "var(--under)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}
