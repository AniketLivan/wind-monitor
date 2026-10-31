# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

UK Wind Forecast Monitor: compares Elexon's WINDFOR wind forecasts with FUELHH actual wind generation for a day-ahead power-buying team. README.md covers the domain, rules and findings in detail; read §3 before touching selection or metrics logic.

## Commands

Python 3.12+ and Node 20+ on the host; no Docker or database server. The data is a committed SQLite file (`backend/data/wind.db`).

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[test]"   # one-time setup
cd backend && .venv/bin/uvicorn app.main:app --reload       # API :8000, docs at /docs
cd backend && .venv/bin/pytest -q                           # backend tests (one file: add the path; one test: -k name)
cd backend && .venv/bin/python -m app.ingest                # rebuild wind.db from Elexon, then commit it
cd frontend && npm install && npm run dev                   # Vite dev server :5173, proxies /api to :8000
cd frontend && npx vitest --run                             # frontend tests (single file: append the path)
cd frontend && npm run build                                # tsc --noEmit + vite build (the only type-check/lint step)
```

- There is no linter/formatter configured.
- Deploys to Vercel: `vercel.json` builds the frontend to static files and routes `/api/*` to `api/index.py`, which imports the FastAPI app from `backend/`. Root `requirements.txt` lists the function's runtime deps (keep it in sync with `backend/pyproject.toml`).

## Architecture

React/Vite frontend → `/api/*` (Vercel rewrite in prod, Vite proxy in dev) → FastAPI → read-only SQLite snapshot. Only the offline ingest script talks to the Elexon BMRS API.

Backend (`backend/app`), the pieces that interact:
- `queries.py` holds the **forecast-selection SQL**: for each actual slot, it picks the latest forecast with `publish_time <= cutoff` (a `max(publish_time)` subquery joined back to the row). Cutoff is either `start_time - horizon_h` or the day-ahead gate (09:20 Europe/London on D-1). SQLite has no time zones, so the gate is computed by `db.day_ahead_cutoff`, registered as an SQL function. Slots with no qualifying forecast get NULL, never a fallback.
- `db.py`: times are stored as fixed-width UTC ISO text (`2026-01-10T12:00:00Z`); use `to_db`/`from_db` at the boundary. `connect()` is read-only + immutable by default; only ingest and tests pass `readonly=False`.
- `metrics.py` is pure Python over the rows `queries.py` returns, with no DB access. `api.py` wires queries → metrics → JSON.
- `elexon.py` (client: weekly chunks, retries, revision de-dup) → `ingest.py` (idempotent upserts into the snapshot).
- `config.py`: scope window, cutoff, DB path (`DATABASE_PATH`) and URLs come from env vars with defaults matching the README; tests override settings through the `get_settings` FastAPI dependency.
- `schema.sql` is applied idempotently by `db.init_schema`.

Frontend (`frontend/src`): `App.tsx` loads data via `api.ts` (types mirror backend JSON in `types.ts`) using `useAsync`; `components/` holds Controls, StatCards and the three Recharts charts.

## Invariants to preserve

- **No look-ahead leakage:** a forecast must never be used for a slot unless `publish_time <= cutoff` (inclusive). The day-ahead cutoff is 09:20 so the 09:30 run on D-1 is excluded.
- Error = `forecast − actual`; positive means over-forecast. The headline "P90 shortfall" is the 90th percentile of positive errors only.
- Accuracy is measured only on on-the-hour slots (forecasts are hourly, actuals half-hourly); the series endpoint still returns half-hourly actuals.
- All times are stored and shown in UTC (scope is January, so GMT = UTC), but the day-ahead cutoff is evaluated in Europe/London.

## Tests

- Backend selection/API tests run against a real SQLite file (a fresh temp file per test via the `conn`/`db_path` fixtures). Seeded forecasts use marker values (see `tests/conftest.py`) so assertions identify exactly which run was picked. Elexon client tests use `httpx.MockTransport`, never the network.
- `docs/superpowers/plans/` holds the original implementation plan; it is history, and the README describes the as-built state.
