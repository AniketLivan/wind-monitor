import pytest

from app.db import init_schema


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True}


def test_health_error_when_database_missing(client, db_settings):
    if db_settings.database_url:
        pytest.skip("SQLite only: deletes the database file")
    db_settings.database_path.unlink()
    assert client.get("/api/health").status_code == 503


def test_init_schema_is_idempotent(conn):
    init_schema(conn)
    n = conn.execute("SELECT count(*) AS n FROM actual_generation").fetchone()["n"]
    assert n == 0
