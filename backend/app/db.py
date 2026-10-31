"""Database access for two backends behind one small API.

* **SQLite** (default, no setup): the committed snapshot `backend/data/wind.db`. This is what
  Vercel serves. Timestamps are stored as fixed-width UTC ISO text (`2026-01-10T12:00:00Z`),
  which sorts and compares correctly as plain strings.
* **Postgres**: used whenever `DATABASE_URL` is set (the Docker Compose setup does this).
  `psycopg` is imported lazily, so the Vercel function doesn't need it installed.

Rows come back as dicts on both. Use `as_dt` for any timestamp column read from either one.
"""

import sqlite3
from datetime import UTC, datetime, time, timedelta
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.config import Settings

UK = ZoneInfo("Europe/London")
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def to_db(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(_FMT)


def from_db(text: str | None) -> datetime | None:
    return datetime.strptime(text, _FMT).replace(tzinfo=UTC) if text else None


def as_dt(value: str | datetime | None) -> datetime | None:
    """A timestamp column as an aware UTC datetime, whichever backend produced it."""
    if value is None:
        return None
    if isinstance(value, str):
        return from_db(value)
    return value.astimezone(UTC)


def is_sqlite(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


def day_ahead_cutoff(start_text: str, cutoff_text: str) -> str:
    """`cutoff` UK local time on the day before the slot's UK delivery date, as UTC text.

    SQLite has no time-zone support, so its SQL calls this as a registered function
    (Postgres does the same maths in SQL)."""
    delivery_day = from_db(start_text).astimezone(UK).date()
    local = datetime.combine(delivery_day - timedelta(days=1), time.fromisoformat(cutoff_text), UK)
    return to_db(local)


def _dict_row(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: value for col, value in zip(cursor.description, row)}


def connect_sqlite(path: Path | str, *, readonly: bool = True) -> sqlite3.Connection:
    """Read-only by default (and immutable, as Vercel's filesystem is read-only); only the
    ingest script and tests open it for writing."""
    if readonly:
        conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro&immutable=1", uri=True)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = _dict_row
    conn.create_function("day_ahead_cutoff", 2, day_ahead_cutoff, deterministic=True)
    return conn


def connect_postgres(url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url, row_factory=dict_row)


def connect(settings: "Settings", *, readonly: bool = True):
    """Postgres when `database_url` is set, otherwise the SQLite snapshot."""
    if settings.database_url:
        return connect_postgres(settings.database_url)
    return connect_sqlite(settings.database_path, readonly=readonly)


def init_schema(conn) -> None:
    name = "schema_sqlite.sql" if is_sqlite(conn) else "schema.sql"
    sql = files("app").joinpath(name).read_text()
    if is_sqlite(conn):
        conn.executescript(sql)
    else:
        conn.execute(sql)
    conn.commit()
