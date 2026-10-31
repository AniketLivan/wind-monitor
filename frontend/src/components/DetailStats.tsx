import { formatMw, formatPct, formatTime } from "../format";
import type { Extreme, Metrics } from "../types";

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

const extreme = (e: Extreme | null) => (e ? formatMw(e.error_mw) : "—");
const when = (e: Extreme | null) => (e ? formatTime(e.start_time) : undefined);

export function DetailStats({ metrics: m }: { metrics: Metrics }) {
  return (
    <section className="stats" aria-label="Detailed accuracy">
      <Stat label="Relative error (nMAE)" value={formatPct(m.nmae_pct)} note="MAE as a share of average actual wind" />
      <Stat label="RMSE" value={formatMw(m.rmse)} note="Penalises big misses" />
      <Stat label="Median miss (P50)" value={formatMw(m.p50_abs)} />
      <Stat label="P90 miss" value={formatMw(m.p90_abs)} />
      <Stat label="P99 miss" value={formatMw(m.p99_abs)} />
      <Stat label="Slots over-forecast" value={formatPct(m.pct_over)} note={`${formatPct(m.pct_under)} under-forecast`} />
      <Stat label="Worst over-forecast" value={extreme(m.max_over)} note={when(m.max_over)} />
      <Stat label="Worst under-forecast" value={extreme(m.max_under)} note={when(m.max_under)} />
    </section>
  );
}
