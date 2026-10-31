import pytest

from conftest import SMALL_ACTUALS, seed_small

DAY = {"start": "2026-01-10", "end": "2026-01-10"}


@pytest.fixture
def seeded(conn):
    seed_small(conn)
    conn.execute("INSERT INTO ingest_log (actual_rows, forecast_rows) VALUES (4, 12)")
    conn.commit()


def point(body, time):
    return next(p for p in body["points"] if p["time"] == time)


def test_series_day_ahead_default(client, seeded):
    r = client.get("/api/series", params=DAY)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "day_ahead"
    assert body["cutoff"] == "09:20"
    p = point(body, "2026-01-10T00:00:00Z")
    assert p["forecast_mw"] == 11
    assert p["forecast_publish_time"] == "2026-01-09T09:20:00Z"
    assert p["error_mw"] == 11 - 500


def test_series_horizon(client, seeded):
    r = client.get("/api/series", params={**DAY, "mode": "horizon", "horizon_h": 1})
    body = r.json()
    assert body["horizon_h"] == 1
    assert point(body, "2026-01-10T12:00:00Z")["forecast_mw"] == 3
    half = point(body, "2026-01-10T00:30:00Z")
    assert half["forecast_mw"] is None and half["error_mw"] is None


def test_metrics_shape(client, seeded):
    series = client.get("/api/series", params=DAY).json()
    body = client.get("/api/metrics", params=DAY).json()
    with_forecast = [p for p in series["points"] if p["forecast_mw"] is not None]
    assert body["metrics"]["n"] == len(with_forecast)
    assert isinstance(body["histogram"], list)


def test_by_horizon_has_49_entries(client, seeded):
    body = client.get("/api/metrics/by-horizon", params=DAY).json()
    assert len(body["horizons"]) == 49
    assert body["horizons"][0]["horizon_h"] == 0
    assert body["day_ahead"]["n"] == 2


def test_reversed_dates_422(client, seeded):
    r = client.get("/api/series", params={"start": "2026-01-11", "end": "2026-01-10"})
    assert r.status_code == 422
    assert r.json()["detail"] == "start must be on or before end"


def test_out_of_scope_422(client, seeded):
    r = client.get("/api/metrics", params={"start": "2026-01-01", "end": "2026-01-10"})
    assert r.status_code == 422
    assert r.json()["detail"] == "dates must be within 2026-01-02 and 2026-02-01"


def test_horizon_out_of_range_422(client, seeded):
    r = client.get("/api/series", params={**DAY, "mode": "horizon", "horizon_h": 49})
    assert r.status_code == 422


def test_meta(client, seeded):
    body = client.get("/api/meta").json()
    assert body["day_ahead_cutoff"] == "09:20"
    assert body["max_horizon_h"] == 48
    assert body["scope"] == {"start_date": "2026-01-02", "end_date": "2026-02-01"}
    assert body["actuals"]["count"] == len(SMALL_ACTUALS)
    assert body["forecasts"]["runs"] == 7  # 10 Jan 07:30 is shared by two groups
    assert body["last_ingest_at"] is not None
