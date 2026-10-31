# UK Wind Forecast Monitor

A web app for a UK energy utility's **day-ahead power buying team**. It shows the latest national wind generation forecast available at the moment a buying decision is made. It also measures how accurate those forecasts have been, so buyers can size how much extra power to buy.

> Status: **v1 built**, backed by a committed SQLite snapshot so it deploys to Vercel with no database to seed. The public repo and the demo video come later (§9).

**Quick start:** see §6 (`uvicorn` for the API, `npm run dev` for the dashboard).

---

## 1. Why this exists

The team buys electricity on the UK day-ahead market, one day before delivery. Wind covers part of their customers' demand, and they buy the rest (e.g. from thermal plants). Wind output depends on the weather, so the amount they buy rests on a **wind forecast made before delivery**. They need to answer two questions:

1. **What does the latest forecast say?** That is, the forecast that was available when the decision had to be made.
2. **How far can I trust it?** How wrong has a forecast made this far ahead been in the past, and in which direction?

### Goals
- Show actual vs. forecast national wind generation for any delivery window in scope.
- Let the user choose the **forecast horizon**: how many hours before delivery the forecast must have been published. A **Day-ahead preset** applies the real market cutoff.
- Measure forecast error for the chosen window and horizon, and show how error grows with horizon.
- Turn the error into a number buyers can act on, e.g. *"to cover 90% of past cases, allow a buffer of X MW"*.

### Non-goals (v1)
- Data other than Elexon FUELHH (WIND) and WINDFOR. No demand, prices, regional data or other fuels.
- Our own forecasting model. We only evaluate Elexon's forecast.
- User accounts, live streaming, alerts.

### Anti-goals (a failure even if it "works")
- **Look-ahead leakage:** using a forecast that wasn't published yet at the decision time. That makes accuracy look better than it really was.
- Error numbers that can't be traced back to the underlying rows.

---

## 2. Data (from Elexon BMRS, checked against live API on 2026-10-27)

Base URL: `https://data.elexon.co.uk/bmrs/api/v1`

| Dataset | Endpoint | Key fields | Observed shape |
|---|---|---|---|
| Actuals | `/datasets/FUELHH/stream?settlementDateFrom=…&settlementDateTo=…&fuelType=WIND` | `startTime`, `generation` (MW), `settlementDate`, `settlementPeriod` | Half-hourly, 48 per day |
| Forecasts | `/datasets/WINDFOR/stream?publishDateTimeFrom=…&publishDateTimeTo=…` | `publishTime`, `startTime`, `generation` (MW) | **Hourly** points; ~8 runs/day (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC); each run spans ~72 h, reaching **~61–66 h ahead** and also including some already-past hours |

Notes:
- **January is GMT**, so UK local time = UTC and there are no clock changes in scope. All times are stored and shown in UTC, labelled "UK time (GMT)".
- Forecast rows whose `startTime` is earlier than their `publishTime` (negative horizon) are dropped.

### Scope window
The brief says "purchase decisions made in **January 2026**". A decision on day D-1 buys for delivery day D, so decisions on 1–31 Jan cover **delivery days 2 Jan – 1 Feb 2026**.
- Actuals loaded: delivery **2 Jan – 1 Feb 2026**. The date picker is limited to this range, and it is also the default view *(my call)*.
- Forecasts loaded: published **29 Dec 2025 – 1 Feb 2026**. This makes sure even early-January slots have forecasts at long horizons.
- The window is set in config, not hard-coded.

---

## 3. Core rules (the parts that must be right)

### 3.1 Which forecast counts for a slot
For a target time `t` and horizon `h` hours:

> Use the **latest** forecast with `publishTime ≤ t − h`, taking the value of that run for `startTime = t`.

If no run meets that condition, the slot shows *no forecast* (a gap, never a guess).

**Day-ahead preset:** for every slot on delivery day D, use the latest forecast with `publishTime ≤ D-1 09:20 UK time`, the GB day-ahead auction gate closure (EPEX). The cutoff is a config value (`DAY_AHEAD_CUTOFF=09:20`) and is covered by boundary tests. Its effective horizon runs from about 14.7 h (00:00 slot) to about 38.2 h (23:30 slot). With the observed publish schedule this is usually the **07:30 run on D-1**. The 09:30 run comes out after the cutoff, so using it would be look-ahead leakage.

Horizon slider: **0–48 h**, 1-hour steps, default = Day-ahead preset.

### 3.2 Half-hourly actuals vs. hourly forecasts *(my call)*
Forecasts exist only on the hour. Accuracy is measured **only on on-the-hour slots**, where both values exist, so no forecast values are invented. The chart still draws actuals at full half-hourly resolution and the forecast as hourly points joined by a line.

### 3.3 Error metrics
Error is defined as `forecast − actual` (MW). **Positive = over-forecast**: less wind came than expected, so the buyer bought too little.

| Metric | Why a buyer cares |
|---|---|
| MAE (mean absolute error) | Typical size of a miss |
| RMSE | Penalises big misses |
| Bias (mean error) | Does the forecast run high or low? |
| nMAE (MAE ÷ mean actual, %) | Size of a miss relative to how much wind there was. Used instead of MAPE, which blows up when wind is low |
| **P90 shortfall** (90th percentile of positive error, i.e. over-forecasts only) | **Headline buffer:** "in 90% of slots, wind fell short of the forecast by less than X MW". One-sided, because only over-forecasts leave the buyer short *(my call)* |
| P50 / P90 / P99 of absolute error | Overall spread of misses in both directions |
| Max over- / under-forecast, with timestamps | Worst cases, so they can be looked into |
| % of slots over- vs. under-forecast | Direction of risk |

Also: **error vs. horizon** (MAE and P90 for h = 0…48) and an **error distribution** histogram for the chosen horizon.

---

## 4. Architecture

```
┌────────────┐   HTTP/JSON   ┌──────────────┐   SQL   ┌────────────┐
│  frontend  │ ────────────▶ │   backend    │ ──────▶ │   SQLite   │
│ React+Vite │               │   FastAPI    │         │            │
└────────────┘               └──────┬───────┘         └────────────┘
                                    ▲ built offline by `python -m app.ingest`
                                    │
                             Elexon BMRS API
```

The data is a frozen January 2026 snapshot in one **SQLite file**, `backend/data/wind.db`, committed to the repo. The backend opens it read-only, so nothing needs seeding on deploy. On **Vercel**, the Vite build is served as static files and `/api/*` is routed to a Python function (`api/index.py`) that runs the FastAPI app.

- **Ingest:** fetches both datasets in week-sized chunks with retries, and upserts them so a re-run is safe and adds no duplicates. Run it locally with `python -m app.ingest` and commit the resulting `wind.db`; the deployed app never writes.
- **Forecast selection** happens in SQL (a `max(publish_time)` subquery per slot, served by the `(publish_time, start_time)` primary key). The 09:20 London cutoff is computed by a Python function registered with SQLite, since SQLite has no time zones.
- **Metrics** are plain Python functions over the joined rows, kept separate from the DB so they're easy to unit-test.

### Database schema
```sql
actual_generation (
  start_time         timestamptz PRIMARY KEY,
  settlement_date    date,
  settlement_period  smallint,
  generation_mw      integer NOT NULL,
  ingested_at        timestamptz DEFAULT now()
)

wind_forecast (
  publish_time   timestamptz,
  start_time     timestamptz,
  generation_mw  integer NOT NULL,
  ingested_at    timestamptz DEFAULT now(),
  PRIMARY KEY (publish_time, start_time)
)
-- index on wind_forecast (start_time, publish_time DESC)
```

### API
| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness + DB check |
| `GET /api/meta` | Data coverage, last ingest time, forecast runs loaded |
| `GET /api/series?start=&end=&horizon_h=` or `&mode=day_ahead` | Per-slot: time, actual, forecast, forecast publish time, error |
| `GET /api/metrics?start=&end=&horizon_h=` / `&mode=day_ahead` | The metrics in §3.3 |
| `GET /api/metrics/by-horizon?start=&end=` | MAE / RMSE / bias / P90 for h = 0…48 |

### Frontend
One dashboard page:
- **Controls:** delivery date range (limited to the scope window), horizon slider plus a *Day-ahead* toggle.
- **Headline cards:** MAE, bias, P90 buffer, nMAE.
- **Main chart:** actual vs. forecast over time, with a hover tooltip that shows the forecast's publish time.
- **Error vs. horizon chart** and **error distribution chart**.

Built with React + TypeScript + Vite, and Recharts for the charts.

---

## 5. Repository layout

```
.
├── docker-compose.yml            # db, backend, frontend
├── docker-compose.override.yml   # dev only: mounts backend source so tests run without rebuilding
├── db/init.sql                   # creates the wind_test database used by the backend tests
├── docs/superpowers/plans/       # step-by-step implementation plan this was built from
├── backend/
│   ├── Dockerfile  pyproject.toml
│   ├── entrypoint.sh             # load data if DB is empty, then start uvicorn
│   ├── app/
│   │   ├── main.py               # FastAPI app factory + /api/health
│   │   ├── api.py                # /api/series, /api/metrics, /api/metrics/by-horizon, /api/meta
│   │   ├── config.py             # scope window, cutoff, DB URL, Elexon base URL (env-overridable)
│   │   ├── db.py  schema.sql     # connection + idempotent schema
│   │   ├── elexon.py             # API client: weekly chunks, retries, revision de-dup
│   │   ├── ingest.py             # upsert into Postgres; CLI `python -m app.ingest [--if-empty]`
│   │   ├── queries.py            # forecast-selection SQL (horizon and day-ahead)
│   │   └── metrics.py            # pure error-metric + histogram functions
│   └── tests/                    # pytest: unit tests + selection/API tests against real Postgres
└── frontend/
    ├── Dockerfile                # runs vitest, builds, serves with nginx
    ├── nginx.conf                # static files + /api proxy
    └── src/
        ├── App.tsx               # page layout and data loading
        ├── api.ts  types.ts      # typed API client mirroring backend JSON
        ├── format.ts  useAsync.ts
        └── components/           # Controls, StatCards, SeriesChart, HorizonChart, ErrorHistogram, Status
```

---

## 6. Running it

Requires Docker (with Compose v2). Nothing else needs to be installed on the host.

```bash
docker compose up --build
# dashboard: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

On the first start the backend loads the scope window from Elexon (~1,500 actuals and ~16,000 forecast rows, a few seconds), then serves. Later starts reuse the data in the `pgdata` volume.

| Task | Command |
|---|---|
| Re-load / refresh data from Elexon | `docker compose run --rm backend python -m app.ingest` |
| Start from an empty database | `docker compose down -v && docker compose up --build` |
| Backend tests (36) | `docker compose run --rm backend pytest -q` |
| Frontend tests (8) | run on every frontend image build, or `cd frontend && npx vitest --run` |
| Frontend dev server (hot reload) | `cd frontend && npm install && npm run dev` → http://localhost:5173 (proxies `/api` to :8000) |

### Testing approach
- **Forecast selection** is tested against a real Postgres (the `wind_test` database), with seeded forecast runs whose values identify the run. Each test asserts exactly which run was picked, including the `<=` boundary, the 09:20 boundary, midnight slots and half-hour slots with no forecast.
- **Metrics** are pure functions tested with hand-calculated numbers.
- **Elexon client** is tested with `httpx.MockTransport`: filtering, revisions, weekly chunking and retry/backoff. Tests never hit the network.
- **API** tests cover response shape, validation errors (422) and the meta endpoint.
- **Frontend** tests cover query building, error messages and empty/no-data rendering. The frontend image build fails if any test fails.

## 7. First findings (January 2026, day-ahead 09:20 cutoff)

| | |
|---|---|
| Typical miss (MAE) | ~2,020 MW (nMAE ~18%) |
| Bias | **+1,750 MW**: the forecast was higher than the outcome in ~85% of hourly slots |
| P90 shortfall buffer | ~4,150 MW |
| Error vs horizon | MAE rises from ~1,690 MW (1 h ahead) to ~2,300 MW (48 h ahead) |

The strong over-forecast bias is the headline for buyers: buying to the forecast would have left them short most of the time. A likely contributor is that FUELHH is metered output after curtailment, while WINDFOR forecasts available wind. This has not been verified yet and would be worth confirming with the client.

## 8. Build plan

1. **Skeleton:** Compose file, Postgres, FastAPI health endpoint, Vite app talking to it.
2. **Ingest:** Elexon client, schema, idempotent upsert, auto-load on empty DB.
3. **Selection:** horizon and day-ahead SQL. Tests for the cutoff (`≤`), gaps, negative horizons and the 09:20 boundary.
4. **Metrics:** pure functions plus tests with hand-computed fixtures. `/series`, `/metrics` and `/by-horizon` endpoints.
5. **Frontend:** controls, cards, the three charts, loading and empty states.
6. **Polish:** README updated to "as built", seeded sanity checks against the live data.

All six are done. The detailed task list is in `docs/superpowers/plans/2026-10-27-wind-forecast-monitor.md`.

---

## 9. Decided later (deliberately out of scope for now)
- Deployment target (Vercel / Heroku), public repo name, demo video.
- The note about AI tools used. **This project is being built with AI assistance (Claude Code)**, and the final README will say so explicitly.
