from __future__ import annotations

from sqlalchemy.engine import Engine

from .config import get_settings
from .db import create_engine_for_url
from .models import Base
from .storage import ensure_schema


def reset_database(engine: Engine) -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    reset_database(engine)
    ensure_schema(engine)
    print("Database schema reset (dropped and recreated).")


if __name__ == "__main__":
    main()


