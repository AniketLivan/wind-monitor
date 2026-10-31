import { type ReactNode, useState } from "react";
import { buildQuery, fetchByHorizon, fetchMeta, fetchMetrics, fetchSeries } from "./api";
import { Controls } from "./components/Controls";
import { DetailStats } from "./components/DetailStats";
import { ErrorHistogram } from "./components/ErrorHistogram";
import { HorizonChart } from "./components/HorizonChart";
import { SeriesChart } from "./components/SeriesChart";
import { StatCards } from "./components/StatCards";
import { Status } from "./components/Status";
import { formatTime } from "./format";
import type { Meta, Selection } from "./types";
import { type Async, useAsync } from "./useAsync";

type Tab = "forecast" | "accuracy";

export function App() {
  const meta = useAsync(fetchMeta, "meta");
  const [tab, setTab] = useState<Tab>("forecast");
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <h1>Wind Forecast Monitor</h1>
          <nav className="tabs" role="tablist" aria-label="Screens">
            {(["forecast", "accuracy"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "tab on" : "tab"}
                onClick={() => setTab(t)}>
                {t === "forecast" ? "Forecast" : "Accuracy"}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <div className="page">
        {meta.status === "loading" && <Status kind="loading" />}
        {meta.status === "error" && <Status kind="error" message={meta.message} />}
        {meta.status === "ok" && <Dashboard meta={meta.data} tab={tab} />}
      </div>
    </>
  );
}

function Dashboard({ meta, tab }: { meta: Meta; tab: Tab }) {
  const [sel, setSel] = useState<Selection>({
    start: meta.scope.start_date, end: meta.scope.end_date, mode: "day_ahead", horizonH: 4,
  });
  const key = buildQuery(sel);
  const metrics = useAsync(() => fetchMetrics(sel), key);
  const series = useAsync(() => fetchSeries(sel), key);
  // Error-by-horizon depends only on the date range, not the horizon being viewed.
  const byHorizon = useAsync(() => fetchByHorizon(sel.start, sel.end), `${sel.start}|${sel.end}`);
  const horizonLabel = sel.mode === "day_ahead" ? `day-ahead (${meta.day_ahead_cutoff} cutoff)` : `${sel.horizonH} h ahead`;

  return (
    <main>
      <Controls value={sel} meta={meta} onChange={setSel} />

      {tab === "forecast" ? (
        <>
          <Loaded state={metrics}>{(d) => <StatCards metrics={d.metrics} />}</Loaded>
          <section className="panel">
            <h2>Actual vs forecast wind generation</h2>
            <p className="panel-sub">Forecast shown is the latest published {horizonLabel}. Hover for the publish time.</p>
            <Loaded state={series}>{(d) => <SeriesChart points={d.points} height={380} />}</Loaded>
          </section>
        </>
      ) : (
        <>
          <Loaded state={metrics}>{(d) => <DetailStats metrics={d.metrics} />}</Loaded>
          <div className="grid-2">
            <section className="panel">
              <h2>Error grows with forecast horizon</h2>
              <p className="panel-sub">Accuracy for the selected dates when forecasts must be published at least N hours ahead.</p>
              <Loaded state={byHorizon}>
                {(d) => <HorizonChart data={d} selectedH={sel.mode === "horizon" ? sel.horizonH : null} />}
              </Loaded>
            </section>
            <section className="panel">
              <h2>Error distribution</h2>
              <p className="panel-sub">Forecast minus actual, hourly slots, {horizonLabel}. 500 MW bins.</p>
              <Loaded state={metrics}>{(d) => <ErrorHistogram bins={d.histogram} />}</Loaded>
            </section>
          </div>
        </>
      )}
      <footer className="footer">
        Source: Elexon BMRS (FUELHH wind actuals, WINDFOR forecasts) · {meta.actuals.count} half-hourly actuals ·{" "}
        {meta.forecasts.runs} forecast runs · last loaded {formatTime(meta.last_ingest_at)} · times are UK (GMT)
      </footer>
    </main>
  );
}

function Loaded<T>({ state, children }: { state: Async<T>; children: (data: T) => ReactNode }) {
  if (state.status === "loading") return <Status kind="loading" />;
  if (state.status === "error") return <Status kind="error" message={state.message} />;
  return <>{children(state.data)}</>;
}
