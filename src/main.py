from src.config import setup_logging
from src.email_store_service import EmailStoreService
from src.rule_processor_service import RuleProcessorService

def main():
    """Main application entry point with proper logging setup."""
    # Set up logging - you can customize these parameters
    setup_logging(
        level="INFO",  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Get logger for main module
    from src.config import get_logger
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


if __name__ == "__main__":
    main()
