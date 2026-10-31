from app.db import init_schema


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True}


def test_init_schema_is_idempotent(conn):
    init_schema(conn)
    row = conn.execute("SELECT to_regclass('wind_forecast_start_pub_idx') AS idx").fetchone()
    assert row["idx"] is not None
