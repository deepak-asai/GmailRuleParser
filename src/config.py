from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str


def build_database_url_from_parts(
    *,
    user: str,
    password: str,
    host: str,
    port: int,
    db_name: str,
) -> str:
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


def get_settings() -> Settings:
    # Load .env if present
    load_dotenv(override=False)

    database_url: Optional[str] = os.getenv("DATABASE_URL")
    if database_url:
        return Settings(database_url=database_url)

    host = os.getenv("DB_HOST")
    port_str = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(f"Invalid DB_PORT: {port_str}")

    url = build_database_url_from_parts(
        user=user, password=password, host=host, port=port, db_name=db_name
    )
    return Settings(database_url=url)


