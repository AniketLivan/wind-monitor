"""HTTP API: actual vs forecast series, error metrics, error by horizon, data coverage."""

from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import connect
from app.metrics import compute_metrics, histogram
from app.queries import SeriesRow, select_series_day_ahead, select_series_horizon

UK = ZoneInfo("Europe/London")
Mode = Literal["horizon", "day_ahead"]

router = APIRouter(prefix="/api")


# ---------- response models ----------

class Point(BaseModel):
    time: datetime
    actual_mw: int
    forecast_mw: int | None
    forecast_publish_time: datetime | None
    error_mw: int | None


class SeriesResponse(BaseModel):
    mode: Mode
    horizon_h: int | None
    cutoff: str | None
    points: list[Point]


class ExtremeOut(BaseModel):
    error_mw: int
    start_time: datetime


class MetricsOut(BaseModel):
    n: int
    mae: float | None
    rmse: float | None
    bias: float | None
    nmae_pct: float | None
    p50_abs: float | None
    p90_abs: float | None
    p99_abs: float | None
    p90_shortfall: float | None
    max_over: ExtremeOut | None
    max_under: ExtremeOut | None
    pct_over: float | None
    pct_under: float | None


class BinOut(BaseModel):
    lo_mw: int
    hi_mw: int
    count: int


class MetricsResponse(BaseModel):
    mode: Mode
    horizon_h: int | None
    metrics: MetricsOut
    histogram: list[BinOut]


class HorizonSummary(BaseModel):
    n: int
    mae: float | None
    rmse: float | None
    bias: float | None
    p90_shortfall: float | None


class HorizonPoint(HorizonSummary):
    horizon_h: int


class ByHorizonResponse(BaseModel):
    horizons: list[HorizonPoint]
    day_ahead: HorizonSummary


# ---------- dependencies ----------

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_conn(settings: SettingsDep) -> Iterator[psycopg.Connection]:
    with connect(settings.database_url) as conn:
        yield conn


ConnDep = Annotated[psycopg.Connection, Depends(get_conn)]


class Window:
    """Delivery days [start, end] (inclusive, UK dates) as a half-open UTC range."""

    def __init__(self, settings: SettingsDep, start: date | None = None, end: date | None = None):
        start = start or settings.delivery_from
        end = end or settings.delivery_to
        if start > end:
            raise HTTPException(422, "start must be on or before end")
        if start < settings.delivery_from or end > settings.delivery_to:
            raise HTTPException(
                422, f"dates must be within {settings.delivery_from} and {settings.delivery_to}"
            )
        self.start = datetime.combine(start, time(), UK).astimezone(UTC)
        self.end = datetime.combine(end + timedelta(days=1), time(), UK).astimezone(UTC)


WindowDep = Annotated[Window, Depends()]
HorizonQ = Annotated[int, Query(ge=0, le=48)]


def _series(conn, settings: Settings, w: Window, mode: Mode, horizon_h: int) -> list[SeriesRow]:
    if mode == "day_ahead":
        return select_series_day_ahead(conn, w.start, w.end, settings.day_ahead_cutoff)
    return select_series_horizon(conn, w.start, w.end, horizon_h)


def _utc(dt: datetime | None) -> datetime | None:
    return dt.astimezone(UTC) if dt else None


def _summary(rows: list[SeriesRow]) -> dict:
    m = compute_metrics(rows)
    return {"n": m.n, "mae": m.mae, "rmse": m.rmse, "bias": m.bias, "p90_shortfall": m.p90_shortfall}


# ---------- routes ----------

@router.get("/series", response_model=SeriesResponse)
def series(conn: ConnDep, settings: SettingsDep, w: WindowDep,
           mode: Mode = "day_ahead", horizon_h: HorizonQ = 4):
    rows = _series(conn, settings, w, mode, horizon_h)
    return SeriesResponse(
        mode=mode,
        horizon_h=horizon_h if mode == "horizon" else None,
        cutoff=settings.day_ahead_cutoff.strftime("%H:%M") if mode == "day_ahead" else None,
        points=[
            Point(
                time=_utc(r.start_time),
                actual_mw=r.actual_mw,
                forecast_mw=r.forecast_mw,
                forecast_publish_time=_utc(r.forecast_publish_time),
                error_mw=None if r.forecast_mw is None else r.forecast_mw - r.actual_mw,
            )
            for r in rows
        ],
    )


@router.get("/metrics", response_model=MetricsResponse)
def metrics(conn: ConnDep, settings: SettingsDep, w: WindowDep,
            mode: Mode = "day_ahead", horizon_h: HorizonQ = 4):
    rows = _series(conn, settings, w, mode, horizon_h)
    return MetricsResponse(
        mode=mode,
        horizon_h=horizon_h if mode == "horizon" else None,
        metrics=MetricsOut(**asdict(compute_metrics(rows))),
        histogram=[BinOut(**asdict(b)) for b in histogram(rows)],
    )


@router.get("/metrics/by-horizon", response_model=ByHorizonResponse)
def metrics_by_horizon(conn: ConnDep, settings: SettingsDep, w: WindowDep):
    horizons = [
        HorizonPoint(horizon_h=h, **_summary(select_series_horizon(conn, w.start, w.end, h)))
        for h in range(settings.max_horizon_h + 1)
    ]
    day_ahead = _summary(select_series_day_ahead(conn, w.start, w.end, settings.day_ahead_cutoff))
    return ByHorizonResponse(horizons=horizons, day_ahead=HorizonSummary(**day_ahead))


@router.get("/meta")
def meta(conn: ConnDep, settings: SettingsDep):
    row = conn.execute(
        """
        SELECT (SELECT count(*) FROM actual_generation) AS actual_count,
               (SELECT min(start_time) FROM actual_generation) AS actual_first,
               (SELECT max(start_time) FROM actual_generation) AS actual_last,
               (SELECT count(DISTINCT publish_time) FROM wind_forecast) AS runs,
               (SELECT min(publish_time) FROM wind_forecast) AS first_publish,
               (SELECT max(publish_time) FROM wind_forecast) AS last_publish,
               (SELECT max(finished_at) FROM ingest_log) AS last_ingest_at
        """
    ).fetchone()
    return {
        "scope": {"start_date": settings.delivery_from, "end_date": settings.delivery_to},
        "day_ahead_cutoff": settings.day_ahead_cutoff.strftime("%H:%M"),
        "max_horizon_h": settings.max_horizon_h,
        "actuals": {"count": row["actual_count"], "first": _utc(row["actual_first"]),
                    "last": _utc(row["actual_last"])},
        "forecasts": {"runs": row["runs"], "first_publish": _utc(row["first_publish"]),
                      "last_publish": _utc(row["last_publish"])},
        "last_ingest_at": _utc(row["last_ingest_at"]),
    }
