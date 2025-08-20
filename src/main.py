#!/usr/bin/env python3
"""
Main entry point for the Gmail Rule Parser application.
Demonstrates proper logging setup and application initialization.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.logging_config import setup_logging
from src.store_emails import EmailStoreService
from src.process_rules import RuleProcessorService


def main():
    """Main application entry point with proper logging setup."""
    # Set up logging - you can customize these parameters
    setup_logging(
        level="INFO",  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_file="logs/app.log",  # Optional: log to file
        log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Get logger for main module
    from src.logging_config import get_logger
    logger = get_logger(__name__)
    
    logger.info("Starting Gmail Rule Parser application")
    
    try:
        # Example: Store emails
        logger.info("Fetching and storing emails...")
        email_service = EmailStoreService()
        total_inserted = email_service.fetch_and_store_emails()
        logger.info(f"Successfully inserted {total_inserted} emails")
        
        # Example: Process rules
        logger.info("Processing rules...")
        rules_path = "src/rules.json"
        service = RuleProcessorService()
        total_processed = service.process_rules_from_file(rules_path)
        logger.info(f"Successfully processed {total_processed} emails across all rules")
        
        logger.info("Application completed successfully")
        
    except Exception as e:
        logger.error(f"Application failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
