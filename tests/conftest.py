import psycopg
import pytest

from app.config import settings


@pytest.fixture(scope="session")
def conn():
    """Live connection to the local corpus DB. Tests using it skip if Postgres isn't up."""
    try:
        connection = psycopg.connect(settings.database_url, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (docker compose up -d)")
    if connection.execute("SELECT count(*) FROM postings").fetchone()[0] == 0:
        pytest.skip("index not built (python -m app.search.indexer)")
    yield connection
    connection.close()
