from __future__ import annotations

from src.gmail_api_service import GmailApiService
from src.db_service import DatabaseService
from src.config import get_logger

# Set up logger for this module
logger = get_logger(__name__)

MAX_PAGES_TO_PROCESS = 10
MAX_RESULTS_PER_PAGE = 50

class EmailStoreService:
    """Service class for fetching and storing emails from Gmail"""
    
    def __init__(self, gmail_api_service: GmailApiService = None, db_service: DatabaseService = None):
        """
        Initialize EmailStoreService with Gmail API and database services.
        
        Args:
            gmail_api_service: Gmail API service instance (creates new one if None)
            db_service: Database service instance (creates new one if None)
        """
        self.gmail_api_service = gmail_api_service or GmailApiService()
        self.db_service = db_service or DatabaseService()
    
    def fetch_and_store_emails(self, max_pages: int = MAX_PAGES_TO_PROCESS, 
                              max_results_per_page: int = MAX_RESULTS_PER_PAGE) -> int:
        """
        Fetch emails from Gmail and store them in the database.
        
        Args:
            max_pages: Maximum number of pages to process
            max_results_per_page: Maximum results per page
            
        Returns:
            Total number of emails inserted
        """
        current_page = 0
        next_page_token = None
        total_inserted = 0
        
        while current_page < max_pages:
            # Fetch message IDs from Gmail
            message_ids, next_page_token = self.gmail_api_service.list_message_ids_in_inbox(
                next_page_token, 
                max_results=max_results_per_page
            )

            # Fetch full messages in batch, then map to DB schema
            results = self.gmail_api_service.get_messages_for_rules_batch(message_ids)
            logger.info(f"Fetched {len(message_ids)} messages from INBOX")
            
            # Store emails in database
            inserted = self.db_service.upsert_emails(results.values())
            total_inserted += inserted
            logger.info(f"Inserted {inserted} emails")

            if not next_page_token:
                break
            current_page += 1
        
        return total_inserted
    
    def store_single_page(self, max_results: int = MAX_RESULTS_PER_PAGE) -> int:
        """
        Fetch and store a single page of emails.
        
        Args:
            max_results: Maximum results to fetch
            
        Returns:
            Number of emails inserted
        """
        # Fetch message IDs from Gmail
        message_ids, _ = self.gmail_api_service.list_message_ids_in_inbox(
            None, 
            max_results=max_results
        )
        logger.info(f"Fetched {len(message_ids)}, {len(set(message_ids))} message ids from INBOX")

        # Fetch full messages in batch, then map to DB schema
        results = self.gmail_api_service.get_messages_for_rules_batch(message_ids)
        logger.info(f"Result count: {len(results)}")
        
        # Store emails in database
        inserted = self.db_service.upsert_emails(results.values())
        logger.info(f"Inserted {inserted} new emails (skipped existing)")
        
        return inserted

def main() -> None:
    """Main function to fetch and store emails"""
    service = EmailStoreService()
    total_inserted = service.fetch_and_store_emails()
    logger.info(f"Total emails inserted: {total_inserted}")


if __name__ == "__main__":
    main()


