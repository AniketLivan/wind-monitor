import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import connect, init_schema
from app.main import create_app

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]


@pytest.fixture
def conn():
    c = connect(TEST_DATABASE_URL)
    init_schema(c)
    c.execute("TRUNCATE actual_generation, wind_forecast, ingest_log")
    c.commit()
    yield c
    c.close()


@pytest.fixture
def client(conn):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: replace(
        get_settings(), database_url=TEST_DATABASE_URL
    )
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
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO actual_generation (start_time, generation_mw) VALUES (%s, %s)",
            list(SMALL_ACTUALS.items()),
        )
        cur.executemany(
            "INSERT INTO wind_forecast (publish_time, start_time, generation_mw) VALUES (%s, %s, %s)",
            SMALL_FORECASTS,
        )
    conn.commit()
