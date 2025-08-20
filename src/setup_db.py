from __future__ import annotations

from src.config import get_settings
from src.db import create_engine_for_url
from src.models import Base
from src.logging_config import get_logger

# Set up logger for this module
logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema created/verified.")


if __name__ == "__main__":
    main()


