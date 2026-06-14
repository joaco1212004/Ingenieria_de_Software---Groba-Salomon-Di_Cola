import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def postgres_url_from_env() -> str:
    user = quote_plus(os.getenv("POSTGRES_USER", "dwh"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "dwh"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "warehouse")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def postgres_engine_from_env() -> Engine:
    return create_engine(postgres_url_from_env(), pool_pre_ping=True)
