from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

def create_engine_for_url(database_url: str) -> Engine:
    from sqlalchemy import create_engine

    # psycopg v3 works with SQLAlchemy 2.x URL: postgresql+psycopg://
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return engine

def get_database_version(engine: Engine) -> str:
    with engine.connect() as connection:
        version = connection.execute(text("select version();")).scalar()
        assert isinstance(version, str)
        return version


