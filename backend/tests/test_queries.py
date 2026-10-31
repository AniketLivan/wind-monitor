from datetime import UTC, datetime, time

import pytest

from app.queries import select_series_day_ahead, select_series_horizon
from conftest import seed_small

DAY_START = datetime(2026, 1, 10, tzinfo=UTC)
DAY_END = datetime(2026, 1, 11, tzinfo=UTC)
CUTOFF = time(9, 20)


@pytest.fixture
def seeded(conn):
    seed_small(conn)
    return conn


def slot(rows, h, m=0):
    return next(r for r in rows if r.start_time == datetime(2026, 1, 10, h, m, tzinfo=UTC))


@pytest.mark.parametrize("horizon_h, expected", [(0, 4), (1, 3), (3, 2), (4, 2), (5, None)])
def test_horizon_picks_latest_eligible(seeded, horizon_h, expected):
    # h=4 → t-4h = 08:00 exactly: the 08:00 run is eligible (<=, boundary).
    rows = select_series_horizon(seeded, DAY_START, DAY_END, horizon_h)
    assert slot(rows, 12).forecast_mw == expected


def test_half_hour_slot_has_no_forecast(seeded):
    row = slot(select_series_horizon(seeded, DAY_START, DAY_END, 0), 0, 30)
    assert row.actual_mw == 510
    assert row.forecast_mw is None
    assert row.forecast_publish_time is None


def test_day_ahead_uses_previous_day_cutoff(seeded):
    row = slot(select_series_day_ahead(seeded, DAY_START, DAY_END, CUTOFF), 0)
    assert row.forecast_mw == 11  # published exactly at 09:20 on the 9th
    assert row.forecast_publish_time == datetime(2026, 1, 9, 9, 20, tzinfo=UTC)


def test_day_ahead_ignores_runs_after_cutoff(seeded):
    row = slot(select_series_day_ahead(seeded, DAY_START, DAY_END, CUTOFF), 23)
    assert row.forecast_mw == 11


def test_range_is_half_open(seeded):
    rows = select_series_horizon(seeded, DAY_START, datetime(2026, 1, 10, 12, tzinfo=UTC), 0)
    assert [r.start_time.hour for r in rows] == [0, 0]
    assert [r.start_time.minute for r in rows] == [0, 30]
