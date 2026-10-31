from datetime import UTC, datetime

import pytest

from app.metrics import Bin, compute_metrics, histogram, percentile
from app.queries import SeriesRow


def t(h):
    return datetime(2026, 1, 10, h, tzinfo=UTC)


PUB = datetime(2026, 1, 9, 7, 30, tzinfo=UTC)
# errors (forecast - actual): +100, -50, 0, +200; plus one slot with no forecast
ROWS = [
    SeriesRow(t(0), 1000, 1100, PUB),
    SeriesRow(t(1), 1000, 950, PUB),
    SeriesRow(t(2), 1000, 1000, PUB),
    SeriesRow(t(3), 1000, 1200, PUB),
    SeriesRow(t(4), 1000, None, None),
]


def test_basic_metrics():
    m = compute_metrics(ROWS)
    assert m.n == 4
    assert m.mae == 87.5
    assert m.bias == 62.5
    assert m.rmse == pytest.approx(114.564, rel=1e-3)
    assert m.nmae_pct == 8.75
    assert m.pct_over == 50.0
    assert m.pct_under == 25.0


def test_percentiles():
    m = compute_metrics(ROWS)
    assert m.p50_abs == 75.0
    assert m.p90_shortfall == 170.0


def test_extremes():
    m = compute_metrics(ROWS)
    assert (m.max_over.error_mw, m.max_over.start_time) == (200, t(3))
    assert (m.max_under.error_mw, m.max_under.start_time) == (-50, t(1))


def test_empty():
    m = compute_metrics([SeriesRow(t(0), 1000, None, None)])
    assert m.n == 0
    assert m.mae is None
    assert m.max_over is None


def test_histogram_bins():
    assert histogram(ROWS, bin_mw=100) == [
        Bin(-100, 0, 1), Bin(0, 100, 1), Bin(100, 200, 1), Bin(200, 300, 1)
    ]


def test_histogram_empty():
    assert histogram([], bin_mw=100) == []


def test_percentile_linear_interpolation():
    assert percentile([0, 0, 100, 200], 90) == 170.0
    with pytest.raises(ValueError):
        percentile([], 50)
