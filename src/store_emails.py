from __future__ import annotations

import time

from .config import get_settings
from .db import create_engine_for_url, get_database_version
from .gmail_api import get_gmail_service, list_message_ids_in_inbox, get_messages_for_rules_batch
from .storage import ensure_schema, upsert_emails


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)

    try:
        version = get_database_version(engine)
        print(f"Connected to Postgres: {version}")
    except Exception as exc:
        print("Could not connect to Postgres")
        return
        

    service = get_gmail_service()
    message_ids = list_message_ids_in_inbox(service, max_results=50)
    print(f"Fetched {len(message_ids)}, {len(set(message_ids))} message ids from INBOX")

    # Fetch full messages in batch, then map to DB schema
    results = get_messages_for_rules_batch(service, message_ids)
    print("Result count: ", len(results))
    inserted = upsert_emails(engine, results.values())
    print(f"Inserted {inserted} new emails (skipped existing)")


if __name__ == "__main__":
    main()


