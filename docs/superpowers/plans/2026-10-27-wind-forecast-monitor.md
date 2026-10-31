# UK Wind Forecast Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Dockerised web app that shows the national wind forecast that was available at decision time for January 2026 day-ahead purchases. It measures forecast error by horizon.

**Architecture:** FastAPI backend loads Elexon FUELHH (WIND) + WINDFOR into Postgres, picks the right forecast per slot in SQL, and computes metrics in pure Python. React (Vite + TS + Recharts) dashboard served by nginx, which proxies `/api` to the backend. All three run through `docker compose`.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, psycopg 3, httpx, pytest · Postgres 16 · Node 20, React 18, TypeScript, Vite, Recharts, Vitest + Testing Library · nginx.

**Spec:** `README.md` (sections 2–4 are the authority. Read them before any task.)

## Global Constraints

- Data sources: only Elexon `FUELHH` (`fuelType=WIND`) and `WINDFOR`, base URL `https://data.elexon.co.uk/bmrs/api/v1`.
- Delivery scope: **2026-01-02 to 2026-02-01 inclusive**. Forecasts loaded by publish time **2025-12-29T00:00Z to 2026-02-02T00:00Z**. These live in config, not hard-coded in logic.
- Forecast rule: latest run with `publish_time <= start_time - horizon`, using `<=`, never `<`. No match → forecast is null, never filled in.
- Day-ahead rule: latest run with `publish_time <= (delivery_date - 1 day) 09:20 Europe/London`. Cutoff comes from config `DAY_AHEAD_CUTOFF=09:20`.
- Horizon range: integer hours **0–48**.
- Error = `forecast_mw - actual_mw`. Positive = over-forecast.
- Metrics count only slots where both actual and forecast exist (on-the-hour slots).
- Forecast rows with `start_time < publish_time` are dropped at parse time.
- All timestamps stored as `timestamptz` and returned as ISO-8601 UTC (`Z`).
- Everything builds and runs with `docker compose`. No host Python or Node needed.
- Commit after each task. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Exact boundary publish time:** a run published exactly at `t − h`, or exactly at 09:20 on D-1, must be selected. *(Task 4 tests.)*
2. **Midnight slots in day-ahead mode:** the 00:00 slot of day D uses D-1 09:20, not D 09:20. *(Task 4 test.)*
3. **Re-running ingest, or Elexon sending revised/duplicate rows:** no duplicate rows, and the latest value wins. A transient 5xx is retried. *(Tasks 2 and 3 tests.)*
4. **Dates outside scope, or reversed:** the API answers 422 with a readable message instead of returning empty numbers. *(Task 6 tests.)*
5. **Backend down or empty result:** the UI shows a clear error or "no data" state, not a blank chart or `NaN`. *(Task 7 and Task 8 tests.)*

---

## File structure

```
docker-compose.yml          # db, backend, frontend
.gitignore
db/init.sql                 # creates wind_test database for tests
backend/
  Dockerfile  pyproject.toml  entrypoint.sh
  app/config.py             # Settings (env → dataclass)
  app/db.py  app/schema.sql # connection + idempotent schema
  app/elexon.py             # HTTP client, chunking, retries, parsing
  app/ingest.py             # upserts, ingest_log, CLI
  app/queries.py            # forecast-selection SQL → SeriesRow
  app/metrics.py            # pure metric + histogram functions
  app/api.py                # pydantic response models + routes
  app/main.py               # FastAPI app factory
  tests/conftest.py  tests/test_*.py
frontend/
  Dockerfile  nginx.conf  package.json  vite.config.ts  index.html
  src/api.ts  src/types.ts  src/App.tsx  src/format.ts
  src/components/{Controls,StatCards,SeriesChart,HorizonChart,ErrorHistogram,Status}.tsx
  src/**/*.test.ts(x)
```

---

### Task 1: Skeleton (repo, compose, schema, health)

**Files:**
- Create: `.gitignore`, `docker-compose.yml`, `db/init.sql`, `backend/Dockerfile`, `backend/pyproject.toml`, `backend/entrypoint.sh`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/schema.sql`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `config.Settings` (frozen dataclass): `database_url: str`, `elexon_base_url: str`, `delivery_from: date`, `delivery_to: date`, `forecast_publish_from: datetime`, `forecast_publish_to: datetime`, `day_ahead_cutoff: time`, `max_horizon_h: int`. `config.get_settings() -> Settings` reads the env vars `DATABASE_URL`, `ELEXON_BASE_URL`, `DELIVERY_FROM`, `DELIVERY_TO`, `FORECAST_PUBLISH_FROM`, `FORECAST_PUBLISH_TO`, `DAY_AHEAD_CUTOFF`, `MAX_HORIZON_H`, with the Global Constraints values as defaults.
  - `db.connect(url: str) -> psycopg.Connection` (autocommit off, `row_factory=dict_row`), `db.init_schema(conn) -> None` (runs `schema.sql`, safe to run twice).
  - Tables: `actual_generation`, `wind_forecast` (exactly as in README §4), plus `ingest_log(id serial PK, finished_at timestamptz NOT NULL DEFAULT now(), actual_rows int NOT NULL, forecast_rows int NOT NULL)`. Index `wind_forecast_start_pub_idx ON wind_forecast (start_time, publish_time DESC)`.
  - `main.create_app() -> FastAPI`, module-level `app = create_app()`. `GET /api/health` → `{"status":"ok","db":true}`, or HTTP 503 with `db:false`.
  - Pytest fixture `conn` in `conftest.py`: connects to `TEST_DATABASE_URL`, runs `init_schema`, then `TRUNCATE actual_generation, wind_forecast, ingest_log` before each test. Fixture `client`: `TestClient(create_app())` with `get_settings` overridden to use `TEST_DATABASE_URL`.
- Compose: `db` (postgres:16, healthcheck `pg_isready`, mounts `db/init.sql`, volume `pgdata`), `backend` (port 8000, env `DATABASE_URL=postgresql://wind:wind@db:5432/wind`, `TEST_DATABASE_URL=…/wind_test`, depends on db healthy, healthcheck on `/api/health`), `frontend` (added in Task 7).

- [ ] **Step 1:** `git init`. Add `.gitignore` (Python, Node, `.env`, `pgdata`).
- [ ] **Step 2: Write failing tests** in `test_health.py`:
  - `test_health_ok(client)`: `GET /api/health` → 200, `{"status":"ok","db":True}`.
  - `test_init_schema_is_idempotent(conn)`: calling `init_schema(conn)` a second time raises nothing, and `SELECT to_regclass('wind_forecast_start_pub_idx')` is not null.
- [ ] **Step 3:** Write the compose file, the Dockerfile (python:3.12-slim, `pip install .[test]`), config, db and main. `entrypoint.sh` for now: `exec uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- [ ] **Step 4: Verify:** `docker compose up -d --build db backend && docker compose run --rm backend pytest -q` → 2 passed. `curl localhost:8000/api/health` → `{"status":"ok","db":true}`.
- [ ] **Step 5: Commit:** `chore: project skeleton with compose, schema and health check`

---

### Task 2: Elexon client

**Files:**
- Create: `backend/app/elexon.py`, `backend/tests/test_elexon.py`

**Interfaces:**
- Consumes: `Settings.elexon_base_url`.
- Produces:
  - `@dataclass(frozen=True) ActualRow(start_time: datetime, settlement_date: date, settlement_period: int, generation_mw: int)`
  - `@dataclass(frozen=True) ForecastRow(publish_time: datetime, start_time: datetime, generation_mw: int)`
  - `fetch_actuals(client: httpx.Client, base_url: str, date_from: date, date_to: date) -> list[ActualRow]`: GET `/datasets/FUELHH/stream?settlementDateFrom=…&settlementDateTo=…&fuelType=WIND`, in chunks of at most 7 days (both ends inclusive). Keeps only `fuelType == "WIND"`. When a `startTime` appears more than once, keeps the row with the latest `publishTime`.
  - `fetch_forecasts(client: httpx.Client, base_url: str, publish_from: datetime, publish_to: datetime) -> list[ForecastRow]`: GET `/datasets/WINDFOR/stream?publishDateTimeFrom=…&publishDateTimeTo=…` in 7-day chunks. Drops rows with `startTime < publishTime`. Deduplicates on `(publish_time, start_time)`.
  - Retries: up to 3 attempts on 5xx or `httpx.TransportError`, with backoff `0.5 * 2**attempt` s (the `sleep` function can be injected for tests: `sleep: Callable[[float], None] = time.sleep`). After the last attempt the error is raised.

- [ ] **Step 1: Write failing tests** using `httpx.MockTransport` (no network):
  - `test_fetch_actuals_parses_and_filters`: the mock returns one WIND row and one CCGT row → 1 `ActualRow` with `start_time == datetime(2026,1,2,0,0,tzinfo=UTC)` and `generation_mw == 14202`.
  - `test_fetch_actuals_keeps_latest_revision`: the same `startTime` twice, with publishTimes `…T00:30Z` (gen 100) and `…T01:00Z` (gen 120) → one row, gen 120.
  - `test_fetch_actuals_chunks_by_week`: range 2026-01-02 to 2026-02-01 → the mock sees 5 requests, and the first `settlementDateTo` is `2026-01-08`.
  - `test_fetch_forecasts_drops_past_rows`: publish `2026-01-01T02:30Z`, starts `2025-12-31T21:00Z` and `2026-01-01T03:00Z` → only the 03:00 row is kept.
  - `test_retries_then_succeeds`: the mock returns 503, 503, then 200 → result returned, and `sleep` called with `[0.5, 1.0]`.
  - `test_retries_exhausted_raises`: always 503 → raises `httpx.HTTPStatusError`.
- [ ] **Step 2:** `docker compose run --rm backend pytest tests/test_elexon.py -q` → fails (import error).
- [ ] **Step 3:** Implement `elexon.py` to the interfaces above.
- [ ] **Step 4:** Same command → 6 passed.
- [ ] **Step 5: Commit:** `feat: Elexon FUELHH/WINDFOR client with chunking and retries`

---

### Task 3: Ingest

**Files:**
- Create: `backend/app/ingest.py`, `backend/tests/test_ingest.py`
- Modify: `backend/entrypoint.sh`

**Interfaces:**
- Consumes: `fetch_actuals`, `fetch_forecasts`, `ActualRow`, `ForecastRow`, `Settings`, `db.connect`, `db.init_schema`.
- Produces:
  - `upsert_actuals(conn, rows: Iterable[ActualRow]) -> int` and `upsert_forecasts(conn, rows: Iterable[ForecastRow]) -> int`: `INSERT … ON CONFLICT (pk) DO UPDATE SET generation_mw = EXCLUDED.generation_mw, ingested_at = now()`. They return the number of rows sent and commit.
  - `run_ingest(conn, settings: Settings, client: httpx.Client) -> IngestResult`, where `IngestResult(actual_rows: int, forecast_rows: int)`. It writes one `ingest_log` row.
  - `ingest_if_empty(conn, settings, client) -> bool`: runs only when `actual_generation` has 0 rows, and returns whether it ran.
  - CLI: `python -m app.ingest [--if-empty]`.
- `entrypoint.sh`: `python -m app.ingest --if-empty && exec uvicorn …`.

- [ ] **Step 1: Write failing tests** (real Postgres via the `conn` fixture, with fetch functions monkeypatched):
  - `test_upsert_is_idempotent`: upsert the same 3 forecast rows twice → `count(*) == 3`.
  - `test_upsert_updates_value`: upsert an actual with gen 100, then the same `start_time` with gen 120 → the stored value is 120.
  - `test_run_ingest_logs`: with stubbed fetchers returning 2 actuals and 3 forecasts → `IngestResult(2,3)`, and `ingest_log` has 1 row with those counts.
  - `test_ingest_if_empty_skips_when_loaded`: seed 1 actual → returns `False`, and the stub fetchers are never called.
- [ ] **Step 2:** `pytest tests/test_ingest.py -q` → fails.
- [ ] **Step 3:** Implement `ingest.py` and update the entrypoint.
- [ ] **Step 4:** Tests → 4 passed. Then `docker compose down -v && docker compose up -d --build`. Backend logs show the ingest counts, and `SELECT count(*) FROM actual_generation` is about **1488** (31 days × 48).
- [ ] **Step 5: Commit:** `feat: idempotent ingest with auto-load on empty database`

---

### Task 4: Forecast selection

**Files:**
- Create: `backend/app/queries.py`, `backend/tests/test_queries.py`

**Interfaces:**
- Consumes: the tables from Task 1.
- Produces:
  - `@dataclass(frozen=True) SeriesRow(start_time: datetime, actual_mw: int, forecast_mw: int | None, forecast_publish_time: datetime | None)`
  - `select_series_horizon(conn, start: datetime, end: datetime, horizon_h: int) -> list[SeriesRow]`
  - `select_series_day_ahead(conn, start: datetime, end: datetime, cutoff: time) -> list[SeriesRow]`
  - Both return one row per `actual_generation` slot in the half-open range `[start, end)`, ordered by `start_time`. The forecast comes from a `LEFT JOIN LATERAL (… ORDER BY publish_time DESC LIMIT 1)`.
  - Day-ahead cutoff expression: `((date_trunc('day', a.start_time AT TIME ZONE 'Europe/London') - interval '1 day' + %(cutoff)s::time) AT TIME ZONE 'Europe/London')`.

- [ ] **Step 1: Write failing tests.** Seed actuals for `2026-01-10T00:00Z`, `T00:30Z`, `T12:00Z`, `T23:00Z`. Seed forecast runs (value = a marker number):
  - for 12:00: publish 07:30→1, 08:00→2, 09:30→3, 11:30→4 (all on 2026-01-10)
  - for 00:00 and 23:00 on 01-10: publish 2026-01-09 07:30→10, 2026-01-09 09:20→11, 2026-01-09 09:30→12, 2026-01-10 07:30→13

  Tests:
  - `test_horizon_picks_latest_eligible`: slot 12:00 → h=0→4, h=1→3, h=3→2, h=4→2 (publish exactly 08:00 = t−4h, **boundary `<=`**), h=5→None.
  - `test_half_hour_slot_has_no_forecast`: slot 00:30 → `forecast_mw is None` and `actual_mw` is present.
  - `test_day_ahead_uses_previous_day_cutoff`: slot 2026-01-10 00:00 → 11 (published exactly at 09:20, boundary), with `forecast_publish_time == 2026-01-09T09:20Z`.
  - `test_day_ahead_ignores_runs_after_cutoff`: slot 2026-01-10 23:00 → 11. Neither 12 (09:30 D-1) nor 13 (same day) is used.
  - `test_range_is_half_open`: `start=2026-01-10T00:00Z, end=2026-01-10T12:00Z` → 2 rows (00:00, 00:30).
- [ ] **Step 2:** `pytest tests/test_queries.py -q` → fails.
- [ ] **Step 3:** Implement `queries.py`.
- [ ] **Step 4:** Tests → 5 passed.
- [ ] **Step 5: Commit:** `feat: horizon and day-ahead forecast selection`

---

### Task 5: Metrics

**Files:**
- Create: `backend/app/metrics.py`, `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: `SeriesRow`.
- Produces:
  - `percentile(values: Sequence[float], q: float) -> float`: linear interpolation (numpy default, `q` in 0–100). Raises `ValueError` on empty input.
  - `@dataclass Extreme(error_mw: int, start_time: datetime)`
  - `@dataclass Metrics(n: int, mae: float|None, rmse: float|None, bias: float|None, nmae_pct: float|None, p50_abs: float|None, p90_abs: float|None, p99_abs: float|None, p90_shortfall: float|None, max_over: Extreme|None, max_under: Extreme|None, pct_over: float|None, pct_under: float|None)`
  - `compute_metrics(rows: Sequence[SeriesRow]) -> Metrics`: uses only rows with `forecast_mw` not None. Error = forecast − actual. `p90_shortfall = percentile([max(e,0) for e in errors], 90)`. `pct_over` = % of e>0, `pct_under` = % of e<0. `nmae_pct = mae / mean(actual) * 100`. With n=0 everything is None.
  - `@dataclass Bin(lo_mw: int, hi_mw: int, count: int)`, `histogram(rows: Sequence[SeriesRow], bin_mw: int = 500) -> list[Bin]`: contiguous `[lo, hi)` bins aligned to multiples of `bin_mw`. The first bin is `floor(min_error / bin_mw) * bin_mw`, and the last is the bin that contains the max error. Empty input → `[]`.

- [ ] **Step 1: Write failing tests.** Fixture: 4 rows with actual 1000 and forecasts 1100, 950, 1000, 1200 (errors +100, −50, 0, +200), plus 1 row with `forecast_mw=None`.
  - `test_basic_metrics`: n=4, mae=87.5, bias=62.5, rmse≈114.564 (`pytest.approx`, rel 1e-3), nmae_pct=8.75, pct_over=50.0, pct_under=25.0.
  - `test_percentiles`: p50_abs=75.0, p90_shortfall=170.0.
  - `test_extremes`: `max_over.error_mw == 200`, `max_under.error_mw == -50`, with the right `start_time`s.
  - `test_empty`: all rows with null forecasts → `n == 0`, `mae is None`, `max_over is None`.
  - `test_histogram_bins`: errors [−50, 0, 100, 200] with bin 100 → bins [−100,0):1, [0,100):1, [100,200):1, [200,300):1.
- [ ] **Step 2:** `pytest tests/test_metrics.py -q` → fails.
- [ ] **Step 3:** Implement `metrics.py`. Standard library only (`math`, `statistics`).
- [ ] **Step 4:** Tests → 5 passed.
- [ ] **Step 5: Commit:** `feat: forecast error metrics and histogram`

---

### Task 6: API endpoints

**Files:**
- Create: `backend/app/api.py`, `backend/tests/test_api.py`
- Modify: `backend/app/main.py` (include the router and CORS for `http://localhost:5173`)

**Interfaces:**
- Consumes: `select_series_horizon`, `select_series_day_ahead`, `compute_metrics`, `histogram`, `Settings`.
- Common query params: `start: date`, `end: date` (delivery days, **inclusive**, converted to `[start 00:00 London, end+1 00:00 London)`), `mode: Literal["horizon","day_ahead"] = "day_ahead"`, `horizon_h: int = Query(4, ge=0, le=48)` (ignored when `mode=day_ahead`). Defaults: `start=Settings.delivery_from`, `end=Settings.delivery_to`.
- Validation → HTTP 422 with `detail` text: `start > end` → `"start must be on or before end"`. Outside scope → `"dates must be within 2026-01-02 and 2026-02-01"` (built from settings).
- Responses (pydantic models in `api.py`):
  - `GET /api/series` → `{mode, horizon_h|null, cutoff:"09:20"|null, points:[{time, actual_mw, forecast_mw, forecast_publish_time, error_mw}]}`
  - `GET /api/metrics` → `{mode, horizon_h, metrics: Metrics, histogram: [Bin]}`
  - `GET /api/metrics/by-horizon?start&end` → `{horizons:[{horizon_h, n, mae, rmse, bias, p90_shortfall}], day_ahead:{n, mae, rmse, bias, p90_shortfall}}` for h = 0…`max_horizon_h`.
  - `GET /api/meta` → `{scope:{start_date, end_date}, day_ahead_cutoff, max_horizon_h, actuals:{count, first, last}, forecasts:{runs, first_publish, last_publish}, last_ingest_at}`

- [ ] **Step 1: Write failing tests** (`client` + seeded `conn`; reuse the Task 4 seed shape as a helper in `conftest.py`, `seed_small(conn)`):
  - `test_series_day_ahead_default`: `GET /api/series?start=2026-01-10&end=2026-01-10` → 200, `mode=="day_ahead"`, the 00:00 point has `forecast_mw==11` and `error_mw==11-actual`.
  - `test_series_horizon`: `mode=horizon&horizon_h=1` → the 12:00 point has `forecast_mw==3`.
  - `test_metrics_shape`: `/api/metrics?...` → `metrics.n` equals the number of points with a forecast, and `histogram` is a list.
  - `test_by_horizon_has_49_entries`: `len(horizons)==49` and `horizons[0].horizon_h==0`.
  - `test_reversed_dates_422` and `test_out_of_scope_422`: check the exact `detail` strings above.
  - `test_horizon_out_of_range_422`: `horizon_h=49` → 422.
  - `test_meta`: `day_ahead_cutoff=="09:20"`, `max_horizon_h==48`, `actuals.count` matches the seed.
- [ ] **Step 2:** `pytest tests/test_api.py -q` → fails.
- [ ] **Step 3:** Implement `api.py` and wire it into `main.py`.
- [ ] **Step 4:** Whole suite: `docker compose run --rm backend pytest -q` → all pass. Manual check: `curl 'localhost:8000/api/metrics'` on the live data returns `n` > 0 and a finite `mae`.
- [ ] **Step 5: Commit:** `feat: series, metrics, by-horizon and meta endpoints`

---

### Task 7: Frontend shell, controls and stat cards

**Files:**
- Create: `frontend/` (Vite React-TS scaffold, written by hand, not interactive), `frontend/Dockerfile`, `frontend/nginx.conf`, `src/types.ts`, `src/api.ts`, `src/format.ts`, `src/App.tsx`, `src/components/Controls.tsx`, `src/components/StatCards.tsx`, `src/components/Status.tsx`, `src/api.test.ts`, `src/components/StatCards.test.tsx`
- Modify: `docker-compose.yml` (add `frontend`: port `3000:80`, depends on backend)

**Interfaces:**
- Consumes: the Task 6 JSON shapes, mirrored as TS types in `types.ts`.
- Produces:
  - `type Selection = { start: string; end: string; mode: "day_ahead" | "horizon"; horizonH: number }`
  - `buildQuery(sel: Selection): string`. It leaves out `horizon_h` when `mode === "day_ahead"`.
  - `fetchSeries(sel)`, `fetchMetrics(sel)`, `fetchByHorizon(start, end)`, `fetchMeta()`. All of them call `/api/...` and throw `ApiError(message)`, using the response's `detail` when present.
  - `formatMw(v: number | null): string` → `"1,234 MW"` or `"—"` for null. `formatPct(v)` → `"8.8%"` or `"—"`.
  - `<Controls value={Selection} meta={Meta} onChange={(s)=>void} />`: date inputs limited by `meta.scope`, a Day-ahead toggle, and a 0–48 slider that is disabled while Day-ahead is on.
  - `<StatCards metrics={Metrics} />`: four cards, **"Typical miss (MAE)"**, **"Bias"** (with "over-forecast" / "under-forecast" sub-label by sign), **"P90 shortfall buffer"** and **"Relative error (nMAE)"**.
  - `<Status kind="loading"|"error"|"empty" message?: string />`
- Dockerfile: `node:20` build stage runs `npm ci && npm test -- --run && npm run build`. Then `nginx:alpine` serves `dist`, and `nginx.conf` sends `location /api/` to `proxy_pass http://backend:8000`.
- Vite dev server proxy `/api` → `http://localhost:8000`.

- [ ] **Step 1: Write failing tests:**
  - `api.test.ts`: `buildQuery({start:"2026-01-02",end:"2026-02-01",mode:"day_ahead",horizonH:4})` → `"start=2026-01-02&end=2026-02-01&mode=day_ahead"`. With `mode:"horizon"` the result includes `&horizon_h=4`. When fetch is mocked to return a 422 `{detail:"start must be on or before end"}`, `fetchMetrics` rejects with that message.
  - `StatCards.test.tsx`: given bias 62.5, it renders "over-forecast". Given `n: 0` with null fields, it renders "—" and no "NaN".
- [ ] **Step 2:** `cd frontend && npx vitest --run` (inside `docker run --rm -v $PWD:/app -w /app node:20`) → fails.
- [ ] **Step 3:** Implement. `App.tsx` loads meta, holds `Selection` state (default: full scope, day_ahead), fetches metrics when the selection changes, and shows `<Status>` while loading or on error.
- [ ] **Step 4:** Tests pass. `docker compose up -d --build` → http://localhost:3000 shows the controls and four cards with real numbers. Stopping the backend (`docker compose stop backend`) and reloading shows the error status.
- [ ] **Step 5: Commit:** `feat: dashboard shell with controls and headline metrics`

---

### Task 8: Charts

**Files:**
- Create: `src/components/SeriesChart.tsx`, `src/components/HorizonChart.tsx`, `src/components/ErrorHistogram.tsx`, `src/components/SeriesChart.test.tsx`
- Modify: `src/App.tsx`

**Interfaces:**
- Consumes: `SeriesResponse.points`, `ByHorizonResponse`, `MetricsResponse.histogram`, and `formatMw` from Task 7.
- Produces:
  - `<SeriesChart points={SeriesPoint[]} />`: Recharts `ComposedChart`. Actual is a solid line drawn on every half-hour. Forecast is a dashed line with `connectNulls` across the half-hour gaps. Tooltip shows time (UK), actual, forecast, error and *"forecast published <time>"*. With an empty `points` it renders `<Status kind="empty">`.
  - `<HorizonChart data={ByHorizonResponse} selectedH={number|null} />`: MAE and P90 shortfall lines against horizon hours, a `ReferenceLine` at `selectedH`, and a horizontal reference for the day-ahead MAE labelled "Day-ahead (09:20 cutoff)".
  - `<ErrorHistogram bins={Bin[]} />`: a bar chart. Bars with `lo_mw >= 0` are coloured as over-forecast and bars with `hi_mw <= 0` as under-forecast.
- Read the `dataviz` skill before writing the chart code (palette, axes, light/dark).

- [ ] **Step 1: Write a failing test** `SeriesChart.test.tsx`: an empty `points` renders the "No data" status text. A points list with one null forecast renders without throwing (mock `ResizeObserver`).
- [ ] **Step 2:** Run vitest → fails.
- [ ] **Step 3:** Implement the charts and lay them out in `App.tsx`: controls → cards → series chart → (horizon chart | histogram) side by side on wide screens, stacked on narrow ones. Fetch `by-horizon` only when `start`/`end` change.
- [ ] **Step 4:** Tests pass. In the browser at :3000, moving the slider updates the cards, the series chart and the histogram, and the horizon chart's marker moves. Day-ahead toggle → the marker disappears and the cards update.
- [ ] **Step 5: Commit:** `feat: series, error-by-horizon and distribution charts`

---

### Task 9: End-to-end check and README as-built

**Files:**
- Modify: `README.md` (drop the "planned" markers, check §5 against the real tree, add a Testing section)

- [ ] **Step 1:** Fresh run: `docker compose down -v && docker compose up --build`. Ingest finishes, and all three services are healthy.
- [ ] **Step 2: Sanity-check the live data:** `/api/meta` actual count ≈ 1488 and forecast runs ≈ 8/day × ~35 days. `/api/metrics/by-horizon`: MAE at h=48 > MAE at h=1 (error grows with horizon; if not, investigate before continuing). Day-ahead MAE falls between the MAEs at h=14 and h=38.
- [ ] **Step 3:** `docker compose run --rm backend pytest -q` and the frontend image build (which runs vitest) both pass.
- [ ] **Step 4:** Update README to match what was built.
- [ ] **Step 5: Commit:** `docs: README reflects as-built application`
