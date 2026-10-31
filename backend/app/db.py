from importlib.resources import files

import psycopg
from psycopg.rows import dict_row


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row)


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(files("app").joinpath("schema.sql").read_text())
    conn.commit()
