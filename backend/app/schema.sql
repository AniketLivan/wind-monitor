CREATE TABLE IF NOT EXISTS actual_generation (
    start_time         timestamptz PRIMARY KEY,
    settlement_date    date,
    settlement_period  smallint,
    generation_mw      integer NOT NULL,
    ingested_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS wind_forecast (
    publish_time   timestamptz NOT NULL,
    start_time     timestamptz NOT NULL,
    generation_mw  integer NOT NULL,
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (publish_time, start_time)
);

CREATE INDEX IF NOT EXISTS wind_forecast_start_pub_idx
    ON wind_forecast (start_time, publish_time DESC);

CREATE TABLE IF NOT EXISTS ingest_log (
    id             serial PRIMARY KEY,
    finished_at    timestamptz NOT NULL DEFAULT now(),
    actual_rows    integer NOT NULL,
    forecast_rows  integer NOT NULL
);
