from __future__ import annotations

from .config import get_settings
from .db import create_engine_for_url
from .models import Base


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(bind=engine)
    print("Database schema created/verified.")


if __name__ == "__main__":
    main()


