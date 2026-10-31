import { formatMw, formatPct } from "../format";
import type { Metrics } from "../types";

function Card({ label, value, note, primary }: { label: string; value: string; note: string; primary?: boolean }) {
  return (
    <div className={primary ? "card primary" : "card"}>
      <div className="card-label">{label}</div>
      <div className="card-value">{value}</div>
      <div className="card-note">{note}</div>
    </div>
  );
}

export function StatCards({ metrics: m }: { metrics: Metrics }) {
  const biasDir =
    m.bias == null ? "No forecast/actual pairs" : m.bias > 0 ? "Forecast tends to over-forecast" :
    m.bias < 0 ? "Forecast tends to under-forecast" : "No systematic bias";
  return (
    <section className="cards" aria-label="Headline accuracy">
      <Card primary label="P90 shortfall buffer" value={formatMw(m.p90_shortfall)}
        note="In 90% of slots, wind fell short of forecast by less than this" />
      <Card label="Typical miss (MAE)" value={formatMw(m.mae)}
        note={m.n ? `Average absolute error over ${m.n} hourly slots` : "No data"} />
      <Card label="Bias" value={m.bias == null ? "—" : (m.bias > 0 ? "+" : "") + formatMw(m.bias)}
        note={m.pct_over == null ? biasDir : `${biasDir} (${formatPct(m.pct_over)} of slots high)`} />
    </section>
  );
}
