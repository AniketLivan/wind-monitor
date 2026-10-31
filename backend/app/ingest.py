"""Load Elexon actuals and forecasts into the database (SQLite snapshot by default, Postgres if
`DATABASE_URL` is set). Safe to re-run: rows are upserted.

For the Vercel deploy, run it locally with no DATABASE_URL and commit the resulting
backend/data/wind.db; the deployed app only reads it."""

import argparse
import logging
from contextlib import closing
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.db import connect, init_schema, is_sqlite, to_db
from app.elexon import ActualRow, ForecastRow, fetch_actuals, fetch_forecasts

Connection = Any  # sqlite3 or psycopg connection (see app.db)

log = logging.getLogger("ingest")


@dataclass(frozen=True)
class IngestResult:
    actual_rows: int
    forecast_rows: int


def _now(conn) -> str:
    return "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')" if is_sqlite(conn) else "now()"


def _executemany(conn, sql: str, params: list[tuple]) -> None:
    """`sql` is written with `?`; Postgres wants `%s`."""
    if is_sqlite(conn):
        conn.executemany(sql, params)
    else:
        with conn.cursor() as cur:
            cur.executemany(sql.replace("?", "%s"), params)


def upsert_actuals(conn: Connection, rows: Iterable[ActualRow]) -> int:
    if is_sqlite(conn):
        params = [(to_db(r.start_time), r.settlement_date.isoformat(), r.settlement_period, r.generation_mw)
                  for r in rows]
    else:
        params = [(r.start_time, r.settlement_date, r.settlement_period, r.generation_mw) for r in rows]
    _executemany(
        conn,
        f"""
        INSERT INTO actual_generation (start_time, settlement_date, settlement_period, generation_mw)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (start_time) DO UPDATE SET
            settlement_date = EXCLUDED.settlement_date,
            settlement_period = EXCLUDED.settlement_period,
            generation_mw = EXCLUDED.generation_mw,
            ingested_at = {_now(conn)}
        """,
        params,
    )
    conn.commit()
    return len(params)


def upsert_forecasts(conn: Connection, rows: Iterable[ForecastRow]) -> int:
    if is_sqlite(conn):
        params = [(to_db(r.publish_time), to_db(r.start_time), r.generation_mw) for r in rows]
    else:
        params = [(r.publish_time, r.start_time, r.generation_mw) for r in rows]
    _executemany(
        conn,
        f"""
        INSERT INTO wind_forecast (publish_time, start_time, generation_mw)
        VALUES (?, ?, ?)
        ON CONFLICT (publish_time, start_time) DO UPDATE SET
            generation_mw = EXCLUDED.generation_mw,
            ingested_at = {_now(conn)}
        """,
        params,
    )
    conn.commit()
    return len(params)


def run_ingest(conn: Connection, settings: Settings, client: httpx.Client) -> IngestResult:
    actuals = fetch_actuals(client, settings.elexon_base_url, settings.delivery_from, settings.delivery_to)
    forecasts = fetch_forecasts(
        client, settings.elexon_base_url, settings.forecast_publish_from, settings.forecast_publish_to
    )
    result = IngestResult(upsert_actuals(conn, actuals), upsert_forecasts(conn, forecasts))
    _executemany(
        conn,
        "INSERT INTO ingest_log (actual_rows, forecast_rows) VALUES (?, ?)",
        [(result.actual_rows, result.forecast_rows)],
    )
    conn.commit()
    return result


def ingest_if_empty(conn: Connection, settings: Settings, client: httpx.Client) -> bool:
    if conn.execute("SELECT EXISTS (SELECT 1 FROM actual_generation) AS loaded").fetchone()["loaded"]:
        return False
    run_ingest(conn, settings, client)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Elexon wind actuals and forecasts.")
    parser.add_argument("--if-empty", action="store_true", help="skip when data is already loaded")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    settings = get_settings()
    with closing(connect(settings, readonly=False)) as conn, httpx.Client() as client:
        init_schema(conn)
        if args.if_empty:
            ran = ingest_if_empty(conn, settings, client)
            log.info("data already loaded, skipping" if not ran else "initial load done")
        else:
            run_ingest(conn, settings, client)
        row = conn.execute(
            "SELECT (SELECT count(*) FROM actual_generation) AS actuals,"
            " (SELECT count(*) FROM wind_forecast) AS forecasts"
        ).fetchone()
        log.info("database holds %s actual rows, %s forecast rows", row["actuals"], row["forecasts"])


if __name__ == "__main__":
    main()
