"""Forecast error metrics. Error = forecast - actual (MW); positive means over-forecast."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.queries import SeriesRow


@dataclass(frozen=True)
class Extreme:
    error_mw: int
    start_time: datetime


@dataclass(frozen=True)
class Metrics:
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    nmae_pct: float | None = None
    p50_abs: float | None = None
    p90_abs: float | None = None
    p99_abs: float | None = None
    p90_shortfall: float | None = None
    max_over: Extreme | None = None
    max_under: Extreme | None = None
    pct_over: float | None = None
    pct_under: float | None = None


@dataclass(frozen=True)
class Bin:
    lo_mw: int
    hi_mw: int
    count: int


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (numpy's default method), q in 0..100."""
    if not values:
        raise ValueError("percentile of empty sequence")
    s = sorted(values)
    pos = (len(s) - 1) * q / 100
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _paired(rows: Sequence[SeriesRow]) -> list[tuple[SeriesRow, int]]:
    return [(r, r.forecast_mw - r.actual_mw) for r in rows if r.forecast_mw is not None]


def compute_metrics(rows: Sequence[SeriesRow]) -> Metrics:
    paired = _paired(rows)
    n = len(paired)
    if n == 0:
        return Metrics(n=0)

    errors = [e for _, e in paired]
    abs_errors = [abs(e) for e in errors]
    mae = sum(abs_errors) / n
    mean_actual = sum(r.actual_mw for r, _ in paired) / n
    over = max(paired, key=lambda p: p[1])
    under = min(paired, key=lambda p: p[1])

    return Metrics(
        n=n,
        mae=mae,
        rmse=math.sqrt(sum(e * e for e in errors) / n),
        bias=sum(errors) / n,
        nmae_pct=mae / mean_actual * 100 if mean_actual else None,
        p50_abs=percentile(abs_errors, 50),
        p90_abs=percentile(abs_errors, 90),
        p99_abs=percentile(abs_errors, 99),
        p90_shortfall=percentile([max(e, 0) for e in errors], 90),
        max_over=Extreme(over[1], over[0].start_time) if over[1] > 0 else None,
        max_under=Extreme(under[1], under[0].start_time) if under[1] < 0 else None,
        pct_over=100 * sum(e > 0 for e in errors) / n,
        pct_under=100 * sum(e < 0 for e in errors) / n,
    )


def histogram(rows: Sequence[SeriesRow], bin_mw: int = 500) -> list[Bin]:
    errors = [e for _, e in _paired(rows)]
    if not errors:
        return []
    first = math.floor(min(errors) / bin_mw)
    last = math.floor(max(errors) / bin_mw)
    counts = [0] * (last - first + 1)
    for e in errors:
        counts[math.floor(e / bin_mw) - first] += 1
    return [Bin((first + i) * bin_mw, (first + i + 1) * bin_mw, c) for i, c in enumerate(counts)]
