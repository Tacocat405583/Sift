from collections.abc import Iterator

from psycopg import Connection

from app.db import pool

DEV_USER_ID = 1  # single hardcoded user until auth exists


def get_conn() -> Iterator[Connection]:
    """One pooled connection per request; commits on success, rolls back on error."""
    with pool.connection() as conn:
        yield conn
