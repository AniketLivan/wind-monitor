"""Load Elexon actuals and forecasts into Postgres. Safe to re-run: rows are upserted."""

import argparse
import logging
from collections.abc import Iterable
from dataclasses import dataclass

import httpx
import psycopg

from app.config import Settings, get_settings
from app.db import connect, init_schema
from app.elexon import ActualRow, ForecastRow, fetch_actuals, fetch_forecasts

log = logging.getLogger("ingest")


@dataclass(frozen=True)
class IngestResult:
    actual_rows: int
    forecast_rows: int


def upsert_actuals(conn: psycopg.Connection, rows: Iterable[ActualRow]) -> int:
    params = [(r.start_time, r.settlement_date, r.settlement_period, r.generation_mw) for r in rows]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO actual_generation (start_time, settlement_date, settlement_period, generation_mw)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (start_time) DO UPDATE SET
                settlement_date = EXCLUDED.settlement_date,
                settlement_period = EXCLUDED.settlement_period,
                generation_mw = EXCLUDED.generation_mw,
                ingested_at = now()
            """,
            params,
        )
    conn.commit()
    return len(params)


def upsert_forecasts(conn: psycopg.Connection, rows: Iterable[ForecastRow]) -> int:
    params = [(r.publish_time, r.start_time, r.generation_mw) for r in rows]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO wind_forecast (publish_time, start_time, generation_mw)
            VALUES (%s, %s, %s)
            ON CONFLICT (publish_time, start_time) DO UPDATE SET
                generation_mw = EXCLUDED.generation_mw,
                ingested_at = now()
            """,
            params,
        )
    conn.commit()
    return len(params)


def run_ingest(conn: psycopg.Connection, settings: Settings, client: httpx.Client) -> IngestResult:
    actuals = fetch_actuals(client, settings.elexon_base_url, settings.delivery_from, settings.delivery_to)
    forecasts = fetch_forecasts(
        client, settings.elexon_base_url, settings.forecast_publish_from, settings.forecast_publish_to
    )
    result = IngestResult(upsert_actuals(conn, actuals), upsert_forecasts(conn, forecasts))
    conn.execute(
        "INSERT INTO ingest_log (actual_rows, forecast_rows) VALUES (%s, %s)",
        (result.actual_rows, result.forecast_rows),
    )
    conn.commit()
    return result


def ingest_if_empty(conn: psycopg.Connection, settings: Settings, client: httpx.Client) -> bool:
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
    with connect(settings.database_url) as conn, httpx.Client() as client:
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
