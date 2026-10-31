"""Runtime settings, read from environment variables with the README's scope as defaults."""

import os
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

# backend/data/wind.db, the committed January snapshot.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "wind.db"


@dataclass(frozen=True)
class Settings:
    database_url: str | None  # Postgres URL; when unset, the SQLite file at database_path is used
    database_path: Path
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
        database_url=env("DATABASE_URL") or None,
        database_path=Path(env("DATABASE_PATH", str(DEFAULT_DB_PATH))),
        elexon_base_url=env("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"),
        delivery_from=date.fromisoformat(env("DELIVERY_FROM", "2026-01-02")),
        delivery_to=date.fromisoformat(env("DELIVERY_TO", "2026-02-01")),
        forecast_publish_from=datetime.fromisoformat(env("FORECAST_PUBLISH_FROM", "2025-12-29T00:00:00+00:00")),
        forecast_publish_to=datetime.fromisoformat(env("FORECAST_PUBLISH_TO", "2026-02-02T00:00:00+00:00")),
        day_ahead_cutoff=time.fromisoformat(env("DAY_AHEAD_CUTOFF", "09:20")),
        max_horizon_h=int(env("MAX_HORIZON_H", "48")),
    )
