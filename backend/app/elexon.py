"""Client for the Elexon BMRS FUELHH (actuals) and WINDFOR (forecast) stream endpoints."""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx

CHUNK = timedelta(days=7)
MAX_ATTEMPTS = 3

Sleep = Callable[[float], None]


@dataclass(frozen=True)
class ActualRow:
    start_time: datetime
    settlement_date: date
    settlement_period: int
    generation_mw: int


@dataclass(frozen=True)
class ForecastRow:
    publish_time: datetime
    start_time: datetime
    generation_mw: int


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get(client: httpx.Client, url: str, params: dict, sleep: Sleep) -> list[dict]:
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.get(url, params=params, timeout=60)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()
            if attempt == MAX_ATTEMPTS - 1:
                resp.raise_for_status()
        except httpx.TransportError:
            if attempt == MAX_ATTEMPTS - 1:
                raise
        sleep(0.5 * 2**attempt)
    raise AssertionError("unreachable")


def _date_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Inclusive [start, end] split into inclusive chunks of at most 7 days."""
    while start <= end:
        chunk_end = min(start + CHUNK - timedelta(days=1), end)
        yield start, chunk_end
        start = chunk_end + timedelta(days=1)


def _time_chunks(start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
    while start < end:
        chunk_end = min(start + CHUNK, end)
        yield start, chunk_end
        start = chunk_end


def fetch_actuals(
    client: httpx.Client, base_url: str, date_from: date, date_to: date, sleep: Sleep = time.sleep
) -> list[ActualRow]:
    """Half-hourly WIND generation for settlement dates date_from..date_to (inclusive).

    If a slot appears more than once (a revision), the row with the latest publishTime wins.
    """
    latest: dict[datetime, tuple[datetime, ActualRow]] = {}
    for lo, hi in _date_chunks(date_from, date_to):
        params = {"settlementDateFrom": lo.isoformat(), "settlementDateTo": hi.isoformat(), "fuelType": "WIND"}
        for r in _get(client, f"{base_url}/datasets/FUELHH/stream", params, sleep):
            if r.get("fuelType") != "WIND":
                continue
            row = ActualRow(
                start_time=_ts(r["startTime"]),
                settlement_date=date.fromisoformat(r["settlementDate"]),
                settlement_period=int(r["settlementPeriod"]),
                generation_mw=int(r["generation"]),
            )
            published = _ts(r["publishTime"])
            prev = latest.get(row.start_time)
            if prev is None or published >= prev[0]:
                latest[row.start_time] = (published, row)
    return sorted((row for _, row in latest.values()), key=lambda r: r.start_time)


def fetch_forecasts(
    client: httpx.Client, base_url: str, publish_from: datetime, publish_to: datetime,
    sleep: Sleep = time.sleep,
) -> list[ForecastRow]:
    """WINDFOR runs published in [publish_from, publish_to); rows for already-past hours are dropped."""
    rows: dict[tuple[datetime, datetime], ForecastRow] = {}
    for lo, hi in _time_chunks(publish_from, publish_to):
        params = {
            "publishDateTimeFrom": lo.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": hi.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for r in _get(client, f"{base_url}/datasets/WINDFOR/stream", params, sleep):
            row = ForecastRow(_ts(r["publishTime"]), _ts(r["startTime"]), int(r["generation"]))
            if row.start_time >= row.publish_time:
                rows[(row.publish_time, row.start_time)] = row
    return sorted(rows.values(), key=lambda r: (r.publish_time, r.start_time))
