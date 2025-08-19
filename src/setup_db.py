from __future__ import annotations

from .config import get_settings
from .db import create_engine_for_url
from .storage import ensure_schema


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    ensure_schema(engine)
    print("Database schema created/verified.")


if __name__ == "__main__":
    main()


