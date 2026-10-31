import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import connect, init_schema, is_sqlite, to_db
from app.main import create_app

# Every DB-backed test runs on SQLite, and on real Postgres too when TEST_DATABASE_URL is set
# (docker compose sets it).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BACKENDS = [
    "sqlite",
    pytest.param(
        "postgres",
        marks=pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
    ),
]


@pytest.fixture(params=BACKENDS)
def db_settings(request, tmp_path):
    """Settings pointing at a fresh, empty test database of the parametrised kind."""
    base = get_settings()
    if request.param == "postgres":
        return replace(base, database_url=TEST_DATABASE_URL)
    return replace(base, database_url=None, database_path=tmp_path / "wind_test.db")


@pytest.fixture
def conn(db_settings):
    c = connect(db_settings, readonly=False)
    init_schema(c)
    if db_settings.database_url:
        c.execute("TRUNCATE actual_generation, wind_forecast, ingest_log")
        c.commit()
    yield c
    c.close()


@pytest.fixture
def client(conn, db_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: db_settings
    with TestClient(app) as c:
        yield c


def _utc(day, h, m=0):
    from datetime import UTC, datetime

    return datetime(2026, 1, day, h, m, tzinfo=UTC)


# Actuals on 2026-01-10 and forecast runs whose generation value is a marker
# identifying the run, so tests can assert which run was selected.
SMALL_ACTUALS = {_utc(10, 0): 500, _utc(10, 0, 30): 510, _utc(10, 12): 1000, _utc(10, 23): 700}
SMALL_FORECASTS = [
    # target 12:00 on the 10th
    (_utc(10, 7, 30), _utc(10, 12), 1),
    (_utc(10, 8), _utc(10, 12), 2),
    (_utc(10, 9, 30), _utc(10, 12), 3),
    (_utc(10, 11, 30), _utc(10, 12), 4),
    # targets 00:00 and 23:00 on the 10th
    *[(pub, tgt, val) for tgt in (_utc(10, 0), _utc(10, 23)) for pub, val in (
        (_utc(9, 7, 30), 10), (_utc(9, 9, 20), 11), (_utc(9, 9, 30), 12), (_utc(10, 7, 30), 13),
    )],
]


def seed_small(conn):
    # SQLite stores UTC text, Postgres real timestamps; the SQL placeholder differs too.
    t = to_db if is_sqlite(conn) else (lambda dt: dt)
    ph = "?" if is_sqlite(conn) else "%s"
    actuals = [(t(ts), v) for ts, v in SMALL_ACTUALS.items()]
    forecasts = [(t(p), t(ts), v) for p, ts, v in SMALL_FORECASTS]
    cur = conn.cursor()
    cur.executemany(f"INSERT INTO actual_generation (start_time, generation_mw) VALUES ({ph}, {ph})", actuals)
    cur.executemany(
        f"INSERT INTO wind_forecast (publish_time, start_time, generation_mw) VALUES ({ph}, {ph}, {ph})",
        forecasts,
    )
    conn.commit()
