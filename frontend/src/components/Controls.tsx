import type { Meta, Selection } from "../types";

type Props = { value: Selection; meta: Meta; onChange: (s: Selection) => void };

export function Controls({ value, meta, onChange }: Props) {
  const { start_date: min, end_date: max } = meta.scope;
  const dayAhead = value.mode === "day_ahead";
  return (
    <section className="filters" aria-label="Filters">
      <div className="field">
        <span className="field-label">Delivery dates</span>
        <div className="date-range">
          <input type="date" aria-label="From" min={min} max={value.end} value={value.start} required
            onChange={(e) => e.target.value && onChange({ ...value, start: e.target.value })} />
          <span aria-hidden>–</span>
          <input type="date" aria-label="To" min={value.start} max={max} value={value.end} required
            onChange={(e) => e.target.value && onChange({ ...value, end: e.target.value })} />
        </div>
      </div>
      <label className="field toggle">
        <input type="checkbox" checked={dayAhead}
          onChange={(e) => onChange({ ...value, mode: e.target.checked ? "day_ahead" : "horizon" })} />
        <span>Day-ahead<small>{meta.day_ahead_cutoff} the day before</small></span>
      </label>
      <label className={`field slider ${dayAhead ? "disabled" : ""}`}>
        <span className="field-label">
          Forecast horizon <strong className="badge">{dayAhead ? "Day-ahead" : `${value.horizonH} h`}</strong>
        </span>
        <input type="range" min={0} max={meta.max_horizon_h} step={1} value={value.horizonH}
          disabled={dayAhead} aria-label="Forecast horizon in hours"
          onChange={(e) => onChange({ ...value, horizonH: Number(e.target.value) })} />
      </label>
    </section>
  );
}
