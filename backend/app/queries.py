"""Pick, for each actual half-hour slot, the forecast that was available at decision time."""

from dataclasses import dataclass
from datetime import datetime, time

import psycopg


@dataclass(frozen=True)
class SeriesRow:
    start_time: datetime
    actual_mw: int
    forecast_mw: int | None
    forecast_publish_time: datetime | None


# {cutoff} is the latest publish_time a forecast may have for slot `a`.
_SERIES_SQL = """
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

_HORIZON_CUTOFF = "a.start_time - make_interval(hours => %(horizon_h)s)"

# 09:20 (or the configured time) UK local time on the day before the slot's UK delivery date.
_DAY_AHEAD_CUTOFF = (
    "((date_trunc('day', a.start_time AT TIME ZONE 'Europe/London') - interval '1 day'"
    " + %(cutoff)s::time) AT TIME ZONE 'Europe/London')"
)


def _rows(conn: psycopg.Connection, sql: str, params: dict) -> list[SeriesRow]:
    return [SeriesRow(**r) for r in conn.execute(sql, params).fetchall()]


def select_series_horizon(
    conn: psycopg.Connection, start: datetime, end: datetime, horizon_h: int
) -> list[SeriesRow]:
    sql = _SERIES_SQL.format(cutoff=_HORIZON_CUTOFF)
    return _rows(conn, sql, {"start": start, "end": end, "horizon_h": horizon_h})


def select_series_day_ahead(
    conn: psycopg.Connection, start: datetime, end: datetime, cutoff: time
) -> list[SeriesRow]:
    sql = _SERIES_SQL.format(cutoff=_DAY_AHEAD_CUTOFF)
    return _rows(conn, sql, {"start": start, "end": end, "cutoff": cutoff})
