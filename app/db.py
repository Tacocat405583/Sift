from psycopg_pool import ConnectionPool

from app.config import settings

# open=False so importing this module never touches the network;
# the FastAPI lifespan (or a script) opens it explicitly.
pool = ConnectionPool(settings.database_url, min_size=1, max_size=5, open=False)
