from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy import text

from src.config import get_settings
from src.db import create_engine_for_url
from src.models import Base
from src.logging_config import get_logger

# Set up logger for this module
logger = get_logger(__name__)


def reset_database(engine: Engine) -> None:
    Base.metadata.drop_all(bind=engine)
    
    # Create pg_trgm extension for GIN trigram indexes
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.commit()
    
    Base.metadata.create_all(bind=engine)


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    reset_database(engine)
    logger.info("Database schema reset (dropped and recreated).")


if __name__ == "__main__":
    main()


