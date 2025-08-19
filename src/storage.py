from __future__ import annotations

from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import Base, Email

def ensure_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def upsert_emails(engine: Engine, email_rows: Iterable[dict], batch_size: int = 1000) -> int:
    """Insert many emails efficiently; skip duplicates by gmail_message_id.

    Uses PostgreSQL ON CONFLICT DO NOTHING on the unique key.
    Returns number of newly inserted rows.
    """
    inserted_total = 0
    buffer: List[dict] = []
    with Session(engine) as session:
        def flush_buffer() -> int:
            if not buffer:
                return 0
            stmt = (
                pg_insert(Email)
                .values(buffer)
                .on_conflict_do_nothing(index_elements=["gmail_message_id"])
                .returning(Email.id)
            )
            result = session.execute(stmt)
            inserted_ids = list(result.scalars())
            session.commit()
            return len(inserted_ids)

        for row in email_rows:
            buffer.append(row)
            if len(buffer) >= batch_size:
                inserted_total += flush_buffer()
                buffer.clear()

        # flush remaining
        inserted_total += flush_buffer()

    return inserted_total


