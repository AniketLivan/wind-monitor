from datetime import UTC, date, datetime

import httpx
import pytest

from app import ingest
from app.config import get_settings
from app.elexon import ActualRow, ForecastRow
from app.ingest import IngestResult, ingest_if_empty, run_ingest, upsert_actuals, upsert_forecasts


def ts(h, m=0, day=10):
    return datetime(2026, 1, day, h, m, tzinfo=UTC)


def actual(h, gen=1000):
    return ActualRow(ts(h), date(2026, 1, 10), h * 2 + 1, gen)


FORECASTS = [ForecastRow(ts(7, 30), ts(h), 900 + h) for h in (8, 9, 10)]


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def stub_fetchers(monkeypatch):
    calls = []

    def fake_actuals(client, base_url, date_from, date_to):
        calls.append("actuals")
        return [actual(1), actual(2)]

    def fake_forecasts(client, base_url, publish_from, publish_to):
        calls.append("forecasts")
        return FORECASTS

    monkeypatch.setattr(ingest, "fetch_actuals", fake_actuals)
    monkeypatch.setattr(ingest, "fetch_forecasts", fake_forecasts)
    return calls


def count(conn, table):
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


def test_upsert_is_idempotent(conn):
    upsert_forecasts(conn, FORECASTS)
    upsert_forecasts(conn, FORECASTS)
    assert count(conn, "wind_forecast") == 3


def test_upsert_updates_value(conn):
    upsert_actuals(conn, [actual(1, gen=100)])
    upsert_actuals(conn, [actual(1, gen=120)])
    row = conn.execute("SELECT generation_mw FROM actual_generation").fetchone()
    assert row["generation_mw"] == 120


def test_run_ingest_logs(conn, settings, stub_fetchers):
    with httpx.Client() as client:
        result = run_ingest(conn, settings, client)
    assert result == IngestResult(actual_rows=2, forecast_rows=3)
    log = conn.execute("SELECT actual_rows, forecast_rows FROM ingest_log").fetchall()
    assert log == [{"actual_rows": 2, "forecast_rows": 3}]


def test_ingest_if_empty_skips_when_loaded(conn, settings, stub_fetchers):
    upsert_actuals(conn, [actual(1)])
    with httpx.Client() as client:
        assert ingest_if_empty(conn, settings, client) is False
    assert stub_fetchers == []
