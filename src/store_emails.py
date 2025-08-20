from __future__ import annotations

import time

from .config import get_settings
from .db import create_engine_for_url, get_database_version
from .gmail_api import get_gmail_service, list_message_ids_in_inbox, get_messages_for_rules_batch
from .storage import upsert_emails

MAX_PAGES_TO_PROCESS = 10
MAX_RESULTS_PER_PAGE = 50

def fetch_and_store_emails(engine):
    service = get_gmail_service()
    
    current_page = 0
    next_page_token = None
    while current_page < MAX_PAGES_TO_PROCESS:
        message_ids, next_page_token = list_message_ids_in_inbox(service, next_page_token, max_results=MAX_RESULTS_PER_PAGE)
        print(f"Fetched {len(message_ids)}, {len(set(message_ids))} message ids from INBOX")

        # Fetch full messages in batch, then map to DB schema
        results = get_messages_for_rules_batch(service, message_ids)
        print("Result count: ", len(results))
        inserted = upsert_emails(engine, results.values())
        print(f"Inserted {inserted} new emails (skipped existing)")

        if not next_page_token:
            break
        current_page += 1


def main() -> None:
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)

    try:
        version = get_database_version(engine)
        print(f"Connected to Postgres: {version}")
    except Exception as exc:
        print("Could not connect to Postgres")
        return
        
    fetch_and_store_emails(engine)
   


if __name__ == "__main__":
    main()


