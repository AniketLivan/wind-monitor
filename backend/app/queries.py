"""Pick, for each actual half-hour slot, the forecast that was available at decision time.

The rule is identical on both backends (latest forecast with publish_time <= cutoff, NULL when
none qualifies); only the SQL dialect differs.
"""

from dataclasses import dataclass
from datetime import datetime, time

from app.db import as_dt, is_sqlite, to_db


@dataclass(frozen=True)
class SeriesRow:
    start_time: datetime
    actual_mw: int
    forecast_mw: int | None
    forecast_publish_time: datetime | None


# ---------- Postgres ----------

# {cutoff} is the latest publish_time a forecast may have for slot `a`.
_PG_SERIES_SQL = """
SELECT a.start_time, a.generation_mw AS actual_mw,
       f.generation_mw AS forecast_mw, f.publish_time AS forecast_publish_time
FROM actual_generation a
LEFT JOIN LATERAL (
    SELECT generation_mw, publish_time
    FROM wind_forecast
    WHERE start_time = a.start_time AND publish_time <= {cutoff}
    ORDER BY publish_time DESC
    LIMIT 1
) f ON true
WHERE a.start_time >= %(start)s AND a.start_time < %(end)s
ORDER BY a.start_time
"""

_PG_HORIZON_CUTOFF = "a.start_time - make_interval(hours => %(horizon_h)s)"

# 09:20 (or the configured time) UK local time on the day before the slot's UK delivery date.
_PG_DAY_AHEAD_CUTOFF = (
    "((date_trunc('day', a.start_time AT TIME ZONE 'Europe/London') - interval '1 day'"
    " + %(cutoff)s::time) AT TIME ZONE 'Europe/London')"
)

# ---------- SQLite ----------

# No LATERAL in SQLite: find the newest eligible publish_time per slot, then read that run.
_LITE_SERIES_SQL = """
SELECT a.start_time, a.generation_mw AS actual_mw,
       f.generation_mw AS forecast_mw, f.publish_time AS forecast_publish_time
FROM actual_generation a
LEFT JOIN wind_forecast f
  ON f.start_time = a.start_time
 AND f.publish_time = (
        SELECT max(publish_time) FROM wind_forecast
        WHERE start_time = a.start_time AND publish_time <= {cutoff}
     )
WHERE a.start_time >= :start AND a.start_time < :end
ORDER BY a.start_time
"""

_LITE_HORIZON_CUTOFF = "strftime('%Y-%m-%dT%H:%M:%SZ', a.start_time, '-' || :horizon_h || ' hours')"

# Time-zone maths isn't available in SQLite SQL: see db.day_ahead_cutoff.
_LITE_DAY_AHEAD_CUTOFF = "day_ahead_cutoff(a.start_time, :cutoff)"


def _rows(conn, sql: str, params: dict) -> list[SeriesRow]:
    return [
        SeriesRow(
            start_time=as_dt(r["start_time"]),
            actual_mw=r["actual_mw"],
            forecast_mw=r["forecast_mw"],
            forecast_publish_time=as_dt(r["forecast_publish_time"]),
        )
        for r in conn.execute(sql, params).fetchall()
    ]


def select_series_horizon(conn, start: datetime, end: datetime, horizon_h: int) -> list[SeriesRow]:
    if is_sqlite(conn):
        sql = _LITE_SERIES_SQL.format(cutoff=_LITE_HORIZON_CUTOFF)
        params = {"start": to_db(start), "end": to_db(end), "horizon_h": horizon_h}
    else:
        sql = _PG_SERIES_SQL.format(cutoff=_PG_HORIZON_CUTOFF)
        params = {"start": start, "end": end, "horizon_h": horizon_h}
    return _rows(conn, sql, params)


def select_series_day_ahead(conn, start: datetime, end: datetime, cutoff: time) -> list[SeriesRow]:
    if is_sqlite(conn):
        sql = _LITE_SERIES_SQL.format(cutoff=_LITE_DAY_AHEAD_CUTOFF)
        params = {"start": to_db(start), "end": to_db(end), "cutoff": cutoff.strftime("%H:%M")}
    else:
        sql = _PG_SERIES_SQL.format(cutoff=_PG_DAY_AHEAD_CUTOFF)
        params = {"start": start, "end": end, "cutoff": cutoff}
    return _rows(conn, sql, params)
