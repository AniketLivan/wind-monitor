# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

UK Wind Forecast Monitor: compares Elexon's WINDFOR wind forecasts with FUELHH actual wind generation for a day-ahead power-buying team. README.md covers the domain, rules and findings in detail; read §3 before touching selection or metrics logic.

## Commands

Everything runs in Docker Compose (`db` Postgres 16, `backend` FastAPI, `frontend` nginx); nothing but Docker is needed on the host.

```bash
docker compose up --build                                   # dashboard :3000, API docs :8000/docs
docker compose run --rm backend pytest -q                   # backend tests (need the db service + TEST_DATABASE_URL, both set by compose)
docker compose run --rm backend pytest tests/test_queries.py -q            # one file
docker compose run --rm backend pytest tests/test_queries.py -k boundary   # one test
docker compose run --rm backend python -m app.ingest        # re-load data from Elexon
docker compose down -v && docker compose up --build         # start from empty DB
cd frontend && npm install && npm run dev                   # Vite dev server :5173, proxies /api to :8000
cd frontend && npx vitest --run                             # frontend tests (single file: append the path)
cd frontend && npm run build                                # tsc --noEmit + vite build (the only type-check/lint step)
```

- `docker-compose.override.yml` is auto-loaded and mounts `backend/app` and `backend/tests`, so backend edits need no rebuild. Frontend changes do need `--build`.
- The frontend Dockerfile runs vitest before building, so a failing frontend test fails the image build.
- There is no linter/formatter configured.

## Architecture

React/Vite frontend → `/api/*` (nginx proxy in prod, Vite proxy in dev) → FastAPI → Postgres, with an ingest path from the Elexon BMRS API.

Backend (`backend/app`), the pieces that interact:
- `queries.py` holds the **forecast-selection SQL**: for each actual slot, a `LEFT JOIN LATERAL` picks the latest forecast with `publish_time <= cutoff`. Cutoff is either `start_time - horizon_h` or the day-ahead gate (09:20 Europe/London on D-1, computed in SQL). Slots with no qualifying forecast get NULL, never a fallback.
- `metrics.py` is pure Python over the rows `queries.py` returns, with no DB access. `api.py` wires queries → metrics → JSON.
- `elexon.py` (client: weekly chunks, retries, revision de-dup) → `ingest.py` (idempotent upserts; `--if-empty` is used by `entrypoint.sh` at container start).
- `config.py`: scope window, cutoff and URLs come from env vars with defaults matching the README; tests override settings through the `get_settings` FastAPI dependency.
- `schema.sql` is applied idempotently by `db.init_schema`.

Frontend (`frontend/src`): `App.tsx` loads data via `api.ts` (types mirror backend JSON in `types.ts`) using `useAsync`; `components/` holds Controls, StatCards and the three Recharts charts.

## Invariants to preserve

- **No look-ahead leakage:** a forecast must never be used for a slot unless `publish_time <= cutoff` (inclusive). The day-ahead cutoff is 09:20 so the 09:30 run on D-1 is excluded.
- Error = `forecast − actual`; positive means over-forecast. The headline "P90 shortfall" is the 90th percentile of positive errors only.
- Accuracy is measured only on on-the-hour slots (forecasts are hourly, actuals half-hourly); the series endpoint still returns half-hourly actuals.
- All times are stored and shown in UTC (scope is January, so GMT = UTC), but the day-ahead cutoff is evaluated in Europe/London.

## Tests

- Backend selection/API tests run against a real Postgres `wind_test` database (created by `db/init.sql`); the `conn` fixture truncates tables each test. Seeded forecasts use marker values (see `tests/conftest.py`) so assertions identify exactly which run was picked. Elexon client tests use `httpx.MockTransport`, never the network.
- `docs/superpowers/plans/` holds the original implementation plan; it is history, and the README describes the as-built state.
