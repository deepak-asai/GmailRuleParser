from __future__ import annotations

import argparse
from typing import List
from datetime import datetime, timezone, timedelta

from .gmail_api import (
    get_gmail_service,
    mark_as_read,
    mark_as_unread,
    move_message_to_label,
)
from .rules import load_rules_from_file
from .config import get_settings
from .db import create_engine_for_url
from .storage import ensure_schema
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from .models import Email

MAX_MESSAGES_TO_PROCESS = 20

def apply_actions(service, message_ids: List[str], actions: List[dict]) -> None:
    for action in actions:
        mark = action.get("mark")
        if mark == "read":
            mark_as_read(service, message_ids)
        elif mark == "unread":
            mark_as_unread(service, message_ids)

        move_to = action.get("move")
        if isinstance(move_to, str) and move_to.strip():
            move_message_to_label(service, message_ids, move_to.strip(), move_to != "INBOX")


def build_database_query(session, rule):
    """
    Build a SQLAlchemy query based on rule conditions for database filtering.
    """
    query = session.query(Email).filter(Email.processed_at.is_(None))
    
    if not rule.conditions:
        return query
    
    # Build conditions for each rule condition
    db_conditions = []
    
    for condition in rule.conditions:
        field = condition.field
        predicate = condition.predicate
        value = condition.value
        
        if field == "From":
            if predicate == "Contains":
                db_conditions.append(Email.from_address.ilike(f"%{value}%"))
            elif predicate == "DoesNotContain":
                db_conditions.append(~Email.from_address.ilike(f"%{value}%"))
            elif predicate == "Equals":
                db_conditions.append(Email.from_address == value)
            elif predicate == "DoesNotEqual":
                db_conditions.append(Email.from_address != value)
                
        elif field == "To":
            if predicate == "Contains":
                db_conditions.append(Email.to_address.ilike(f"%{value}%"))
            elif predicate == "DoesNotContain":
                db_conditions.append(~Email.to_address.ilike(f"%{value}%"))
            elif predicate == "Equals":
                db_conditions.append(Email.to_address == value)
            elif predicate == "DoesNotEqual":
                db_conditions.append(Email.to_address != value)
                
        elif field == "Subject":
            if predicate == "Contains":
                db_conditions.append(Email.subject.ilike(f"%{value}%"))
            elif predicate == "DoesNotContain":
                db_conditions.append(~Email.subject.ilike(f"%{value}%"))
            elif predicate == "Equals":
                db_conditions.append(Email.subject == value)
            elif predicate == "DoesNotEqual":
                db_conditions.append(Email.subject != value)
                
        elif field == "Message":
            if predicate == "Contains":
                db_conditions.append(Email.snippet.ilike(f"%{value}%"))
            elif predicate == "DoesNotContain":
                db_conditions.append(~Email.snippet.ilike(f"%{value}%"))
            elif predicate == "Equals":
                db_conditions.append(Email.snippet == value)
            elif predicate == "DoesNotEqual":
                db_conditions.append(Email.snippet != value)
                
        elif field == "Received":
            try:
                num = float(value)
                now = datetime.now(timezone.utc)
                
                if predicate == "LessThanDays":
                    cutoff_date = now - timedelta(days=num)
                    db_conditions.append(Email.received_at > cutoff_date)
                elif predicate == "GreaterThanDays":
                    cutoff_date = now - timedelta(days=num)
                    db_conditions.append(Email.received_at < cutoff_date)
                elif predicate == "LessThanMonths":
                    cutoff_date = now - timedelta(days=num * 30)
                    db_conditions.append(Email.received_at > cutoff_date)
                elif predicate == "GreaterThanMonths":
                    cutoff_date = now - timedelta(days=num * 30)
                    db_conditions.append(Email.received_at < cutoff_date)
            except ValueError:
                # If value can't be converted to float, skip this condition
                continue
        else:
            raise ValueError(f"Invalid field: {field}")
    
    # Apply conditions based on rule predicate
    if db_conditions:
        if rule.predicate == "All":
            query = query.filter(and_(*db_conditions))
        else:  # "Any"
            query = query.filter(or_(*db_conditions))
    
    # Print the raw SQL query
    print("Generated SQL Query:")
    print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))
    print("-" * 50)
    
    return query


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Gmail messages based on JSON rules")
    parser.add_argument("rules_pos", nargs="?", default=None, help="Path to rules JSON file (positional)")
    parser.add_argument("--rules", "-r", default="src/rules.json", help="Path to rules JSON file")
    args = parser.parse_args()
    
    # Setup database connection
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    
    # Load rule
    rules_path = args.rules_pos or args.rules
    rule = load_rules_from_file(rules_path)
    service = get_gmail_service()

    # Process messages using database queries
    with Session(engine) as session:
        while True:
            # Build query based on rule conditions
            query = build_database_query(session, rule)
            emails = query.limit(MAX_MESSAGES_TO_PROCESS).all()
            
            print(f"Found {len(emails)} messages matching rule conditions from database...")
            
            # Break if no more emails to process
            if len(emails) == 0:
                print("No more emails matching rule conditions")
                break
            
            matching_message_ids = []
            processed_emails = []
            
            for email in emails:
                # Since we're already filtering at the database level,
                # all emails returned should match the rule
                matching_message_ids.append(email.gmail_message_id)
                
                # Mark as processed
                email.processed_at = datetime.now(timezone.utc)
                processed_emails.append(email)
            
            # Apply actions to matching messages
            if matching_message_ids:
                apply_actions(service, matching_message_ids, rule.actions)
            
            # Commit all processed emails
            session.commit()
            print(f"Processed {len(processed_emails)} emails and marked as processed")


if __name__ == "__main__":
    main()


