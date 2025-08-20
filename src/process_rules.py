from __future__ import annotations

import argparse
from typing import List

from src.gmail_api_v2 import GmailApiService
from .rules import load_rules_from_file
from .storage import DatabaseService

MAX_MESSAGES_TO_PROCESS = 20


def apply_actions(gmail_api_service, message_ids: List[str], actions: List[dict]) -> None:
    """
    Apply actions to a list of message IDs.
    
    Args:
        gmail_api_service: Gmail API service instance
        message_ids: List of Gmail message IDs
        actions: List of actions to apply
    """
    for action in actions:
        mark = action.get("mark")
        if mark == "read":
            gmail_api_service.mark_as_read(message_ids)
        elif mark == "unread":
            gmail_api_service.mark_as_unread(message_ids)

        move_to = action.get("move")
        if isinstance(move_to, str) and move_to.strip():
            # gmail_api_service.move_message_to_label(message_ids, move_to.strip(), move_to != "INBOX")
            gmail_api_service.move_message_to_label(message_ids, move_to.strip(), False) # TODO: Revert to old code


def process_emails_with_rules(gmail_api_service, db_service, rule):
    """
    Process emails using database queries and apply rule actions.
    
    Args:
        gmail_api_service: Gmail API service instance
        db_service: Database service instance
        rule: Rule to apply to emails
    """
    offset = 0
    while True:
        # Get matching emails from database with pagination
        emails = db_service.get_matching_emails(rule, offset=offset, limit=MAX_MESSAGES_TO_PROCESS)
        
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
            apply_actions(gmail_api_service, matching_message_ids, rule.actions)
        
        # Mark emails as processed in database
        # db_service.mark_emails_as_processed(email_ids_to_mark)
        
        print(f"Processed {len(emails)} emails")
        
        # Update offset for next page
        offset += len(emails)


def main() -> None:
    """Main function to process Gmail messages based on JSON rules"""
    parser = argparse.ArgumentParser(description="Process Gmail messages based on JSON rules")
    parser.add_argument("rules_pos", nargs="?", default=None, help="Path to rules JSON file (positional)")
    parser.add_argument("--rules", "-r", default="src/rules.json", help="Path to rules JSON file")
    args = parser.parse_args()
    
    # Load rule
    rules_path = args.rules_pos or args.rules
    rule = load_rules_from_file(rules_path)
    
    # Get services
    gmail_api_service = GmailApiService()
    db_service = DatabaseService()
    
    # Process emails with rules
    process_emails_with_rules(gmail_api_service, db_service, rule)


if __name__ == "__main__":
    main()


