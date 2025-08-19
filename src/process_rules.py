from __future__ import annotations

import argparse
from typing import List

from .gmail_api import (
    get_gmail_service,
    mark_as_read,
    mark_as_unread,
    move_message_to_label,
)
from .rules import load_rules_from_file, message_matches_rule
from .config import get_settings
from .db import create_engine_for_url
from .storage import ensure_schema
from sqlalchemy.orm import Session
from .models import Email


def apply_actions(service, message_id: str, actions: List[dict]) -> None:
    for action in actions:
        mark = action.get("mark")
        if mark == "read":
            mark_as_read(service, message_id)
        elif mark == "unread":
            mark_as_unread(service, message_id)

        move_to = action.get("move")
        if isinstance(move_to, str) and move_to.strip():
            move_message_to_label(service, message_id, move_to.strip(), move_to != "INBOX")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Gmail messages based on JSON rules")
    parser.add_argument("rules_pos", nargs="?", default=None, help="Path to rules JSON file (positional)")
    parser.add_argument("--rules", "-r", default="src/rules.json", help="Path to rules JSON file")
    parser.add_argument("--max", type=int, default=100, help="Max messages to consider from database")
    args = parser.parse_args()
    
    # Setup database connection
    settings = get_settings()
    engine = create_engine_for_url(settings.database_url)
    
    # Load rule
    rules_path = args.rules_pos or args.rules
    rule = load_rules_from_file(rules_path)
    service = get_gmail_service()

    # Fetch messages from database
    with Session(engine) as session:
        emails = session.query(Email).limit(args.max).all()
        print(f"Checking {len(emails)} messages from database against rules...")

        for email in emails:
            # Convert Email model to dict format expected by rules
            msg = {
                "id": email.gmail_message_id,
                "from": email.from_address,
                "to": email.to_address,
                "subject": email.subject or "",
                "message": email.snippet or "",
                "received_at": email.received_at,
                "label_ids": email.label_ids or [],
            }
            
            if message_matches_rule(rule, msg):
                print(f"Message {email.gmail_message_id} matched rule")
                apply_actions(service, email.gmail_message_id, rule.actions)


if __name__ == "__main__":
    main()


