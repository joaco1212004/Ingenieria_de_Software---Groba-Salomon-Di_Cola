import os
from functools import lru_cache
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@lru_cache
def get_engine() -> Engine:
    user = quote_plus(os.getenv("POSTGRES_USER", "dwh"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "dwh"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "warehouse")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url, pool_pre_ping=True)
