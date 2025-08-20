from __future__ import annotations

from src.gmail_api_v2 import GmailApiService
from .storage import upsert_emails

MAX_PAGES_TO_PROCESS = 10
MAX_RESULTS_PER_PAGE = 50

def fetch_and_store_emails(gmail_api_service):
    current_page = 0
    next_page_token = None
    while current_page < MAX_PAGES_TO_PROCESS:
        message_ids, next_page_token = gmail_api_service.list_message_ids_in_inbox(next_page_token, max_results=MAX_RESULTS_PER_PAGE)
        print(f"Fetched {len(message_ids)}, {len(set(message_ids))} message ids from INBOX")

        # Fetch full messages in batch, then map to DB schema
        results = gmail_api_service.get_messages_for_rules_batch(message_ids)
        print("Result count: ", len(results))
        inserted = upsert_emails(results.values())
        print(f"Inserted {inserted} new emails (skipped existing)")

        if not next_page_token:
            break
        current_page += 1

def main() -> None:
    gmail_api_service = GmailApiService()
    fetch_and_store_emails(gmail_api_service)

if __name__ == "__main__":
    main()


