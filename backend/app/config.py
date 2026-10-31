"""Runtime settings, read from environment variables with the README's scope as defaults."""

import os
from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True)
class Settings:
    database_url: str
    elexon_base_url: str
    delivery_from: date
    delivery_to: date
    forecast_publish_from: datetime
    forecast_publish_to: datetime
    day_ahead_cutoff: time
    max_horizon_h: int


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        database_url=env("DATABASE_URL", "postgresql://wind:wind@localhost:5432/wind"),
        elexon_base_url=env("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"),
        delivery_from=date.fromisoformat(env("DELIVERY_FROM", "2026-01-02")),
        delivery_to=date.fromisoformat(env("DELIVERY_TO", "2026-02-01")),
        forecast_publish_from=datetime.fromisoformat(env("FORECAST_PUBLISH_FROM", "2025-12-29T00:00:00+00:00")),
        forecast_publish_to=datetime.fromisoformat(env("FORECAST_PUBLISH_TO", "2026-02-02T00:00:00+00:00")),
        day_ahead_cutoff=time.fromisoformat(env("DAY_AHEAD_CUTOFF", "09:20")),
        max_horizon_h=int(env("MAX_HORIZON_H", "48")),
    )
