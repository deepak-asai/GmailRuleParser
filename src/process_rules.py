from __future__ import annotations

import argparse
from typing import List

from src.gmail_api_v2 import GmailApiService
from .rules import load_rules_from_file, Rule
from .storage import DatabaseService

MAX_MESSAGES_TO_PROCESS = 20


class RuleProcessorService:
    """Service class for processing emails based on rules"""
    
    def __init__(self, gmail_api_service: GmailApiService = None, db_service: DatabaseService = None):
        """
        Initialize RuleProcessorService with Gmail API and database services.
        
        Args:
            gmail_api_service: Gmail API service instance (creates new one if None)
            db_service: Database service instance (creates new one if None)
        """
        self.gmail_api_service = gmail_api_service or GmailApiService()
        self.db_service = db_service or DatabaseService()
    
    def apply_actions(self, message_ids: List[str], actions: List[dict]) -> None:
        """
        Apply actions to a list of message IDs.
        
        Args:
            message_ids: List of Gmail message IDs
            actions: List of actions to apply
        """
        for action in actions:
            mark = action.get("mark")
            if mark == "read":
                self.gmail_api_service.mark_as_read(message_ids)
            elif mark == "unread":
                self.gmail_api_service.mark_as_unread(message_ids)

            move_to = action.get("move")
            if isinstance(move_to, str) and move_to.strip():
                # gmail_api_service.move_message_to_label(message_ids, move_to.strip(), move_to != "INBOX")
                self.gmail_api_service.move_message_to_label(message_ids, move_to.strip(), False) # TODO: Revert to old code
    
    def process_emails_with_rules(self, rule: Rule, max_messages: int = MAX_MESSAGES_TO_PROCESS) -> int:
        """
        Process emails using database queries and apply rule actions.
        
        Args:
            rule: Rule to apply to emails
            max_messages: Maximum messages to process per batch
            
        Returns:
            Total number of emails processed
        """
        offset = 0
        total_processed = 0
        
        while True:
            # Get matching emails from database with pagination
            emails = self.db_service.get_matching_emails(rule, offset=offset, limit=max_messages)
            
            print(f"Found {len(emails)} messages matching rule conditions from database...")
            
            # Break if no more emails to process
            if len(emails) == 0:
                print("No more emails matching rule conditions")
                break
            
            matching_message_ids = []
            email_ids_to_mark = []
            
            for email in emails:
                # Since we're already filtering at the database level,
                # all emails returned should match the rule
                matching_message_ids.append(email.gmail_message_id)
                email_ids_to_mark.append(email.id)
            
            # Apply actions to matching messages
            if matching_message_ids:
                self.apply_actions(matching_message_ids, rule.actions)
            
            print(f"Processed {len(emails)} emails")
            total_processed += len(emails)
            
            # Update offset for next page
            offset += len(emails)
        
        return total_processed
    
    def process_rules_from_file(self, rules_path: str, max_messages: int = MAX_MESSAGES_TO_PROCESS) -> int:
        """
        Load rules from file and process emails.
        
        Args:
            rules_path: Path to rules JSON file
            max_messages: Maximum messages to process per batch
            
        Returns:
            Total number of emails processed
        """
        rule = load_rules_from_file(rules_path)
        return self.process_emails_with_rules(rule, max_messages)


def main() -> None:
    """Main function to process Gmail messages based on JSON rules"""
    parser = argparse.ArgumentParser(description="Process Gmail messages based on JSON rules")
    parser.add_argument("rules_pos", nargs="?", default=None, help="Path to rules JSON file (positional)")
    parser.add_argument("--rules", "-r", default="src/rules.json", help="Path to rules JSON file")
    args = parser.parse_args()
    
    # Load rule path
    rules_path = args.rules_pos or args.rules
    
    # Create service and process
    service = RuleProcessorService()
    total_processed = service.process_rules_from_file(rules_path)
    print(f"Total emails processed: {total_processed}")


if __name__ == "__main__":
    main()


