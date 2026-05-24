from collections.abc import Sequence
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)


@contextmanager
def get_connection() -> Connection:
    with engine.connect() as connection:
        yield connection


def fetch_all(query: str) -> list[dict]:
    with get_connection() as connection:
        result = connection.execute(text(query))
        return [dict(row) for row in result.mappings()]


def fetch_one(query: str) -> dict:
    rows = fetch_all(query)
    return rows[0] if rows else {}


def ping() -> bool:
    with get_connection() as connection:
        result = connection.execute(text("SELECT 1 AS ok"))
        row = result.mappings().one()
        return row["ok"] == 1
