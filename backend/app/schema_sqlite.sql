-- SQLite flavour of schema.sql. Times are UTC ISO text, e.g. 2026-01-10T12:00:00Z (see app/db.py).
CREATE TABLE IF NOT EXISTS actual_generation (
    start_time         TEXT PRIMARY KEY,
    settlement_date    TEXT,
    settlement_period  INTEGER,
    generation_mw      INTEGER NOT NULL,
    ingested_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS wind_forecast (
    publish_time   TEXT NOT NULL,
    start_time     TEXT NOT NULL,
    generation_mw  INTEGER NOT NULL,
    ingested_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (publish_time, start_time)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ingest_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    finished_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    actual_rows    INTEGER NOT NULL,
    forecast_rows  INTEGER NOT NULL
);
