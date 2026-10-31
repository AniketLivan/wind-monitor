from datetime import UTC, date, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from app.elexon import ActualRow, ForecastRow, fetch_actuals, fetch_forecasts

BASE = "https://elexon.test/v1"


def fuel(start, publish, gen, fuel_type="WIND", sp=1):
    return {
        "dataset": "FUELHH", "publishTime": publish, "startTime": start,
        "settlementDate": start[:10], "settlementPeriod": sp,
        "fuelType": fuel_type, "generation": gen,
    }


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_actuals_parses_and_filters():
    rows = [
        fuel("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 14202),
        fuel("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 9000, fuel_type="CCGT"),
    ]
    with client_for(lambda req: httpx.Response(200, json=rows)) as c:
        result = fetch_actuals(c, BASE, date(2026, 1, 2), date(2026, 1, 2))
    assert result == [ActualRow(datetime(2026, 1, 2, 0, 0, tzinfo=UTC), date(2026, 1, 2), 1, 14202)]


def test_fetch_actuals_keeps_latest_revision():
    rows = [
        fuel("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 100),
        fuel("2026-01-02T00:00:00Z", "2026-01-02T01:00:00Z", 120),
    ]
    with client_for(lambda req: httpx.Response(200, json=rows)) as c:
        result = fetch_actuals(c, BASE, date(2026, 1, 2), date(2026, 1, 2))
    assert [r.generation_mw for r in result] == [120]


def test_fetch_actuals_chunks_by_week():
    seen = []

    def handler(req):
        seen.append(parse_qs(req.url.query.decode()))
        return httpx.Response(200, json=[])

    with client_for(handler) as c:
        fetch_actuals(c, BASE, date(2026, 1, 2), date(2026, 2, 1))
    assert len(seen) == 5
    assert seen[0]["settlementDateFrom"] == ["2026-01-02"]
    assert seen[0]["settlementDateTo"] == ["2026-01-08"]
    assert seen[0]["fuelType"] == ["WIND"]
    assert seen[-1]["settlementDateTo"] == ["2026-02-01"]


def test_fetch_forecasts_drops_past_rows():
    rows = [
        {"publishTime": "2026-01-01T02:30:00Z", "startTime": "2025-12-31T21:00:00Z", "generation": 1},
        {"publishTime": "2026-01-01T02:30:00Z", "startTime": "2026-01-01T03:00:00Z", "generation": 2},
    ]
    with client_for(lambda req: httpx.Response(200, json=rows)) as c:
        result = fetch_forecasts(
            c, BASE, datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )
    assert result == [
        ForecastRow(
            datetime(2026, 1, 1, 2, 30, tzinfo=UTC), datetime(2026, 1, 1, 3, 0, tzinfo=UTC), 2
        )
    ]


def test_retries_then_succeeds():
    responses = iter([503, 503, 200])
    sleeps = []

    def handler(req):
        code = next(responses)
        return httpx.Response(code, json=[] if code == 200 else {"error": "busy"})

    with client_for(handler) as c:
        result = fetch_actuals(c, BASE, date(2026, 1, 2), date(2026, 1, 2), sleep=sleeps.append)
    assert result == []
    assert sleeps == [0.5, 1.0]


def test_retries_exhausted_raises():
    with client_for(lambda req: httpx.Response(503)) as c:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_actuals(c, BASE, date(2026, 1, 2), date(2026, 1, 2), sleep=lambda s: None)
