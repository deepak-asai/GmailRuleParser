from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Iterable, List

from sqlalchemy import or_, and_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models import Base, Email
from src.config import get_settings, create_engine_for_url, get_logger
from src.constants import (
    FIELD_FROM, FIELD_TO, FIELD_SUBJECT, FIELD_MESSAGE, FIELD_RECEIVED,
    PREDICATE_CONTAINS, PREDICATE_DOES_NOT_CONTAIN, PREDICATE_EQUALS, PREDICATE_DOES_NOT_EQUAL,
    PREDICATE_LESS_THAN_DAYS, PREDICATE_GREATER_THAN_DAYS, PREDICATE_LESS_THAN_MONTHS, PREDICATE_GREATER_THAN_MONTHS,
    RULE_PREDICATE_ALL, BATCH_SIZE_DEFAULT, DAYS_PER_MONTH, DEFAULT_OFFSET, DEFAULT_LIMIT,
    ERROR_INVALID_FIELD
)

# Set up logger for this module
logger = get_logger(__name__)


def singleton(cls):
    """
    Decorator to make a class a singleton.
    Ensures only one instance of the class exists.
    """
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


@singleton
class DatabaseService:
    """Service class for handling all database operations"""
    
    def __init__(self):
        """Initialize database service with engine"""
        settings = get_settings()
        self.engine = create_engine_for_url(settings.database_url)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return Session(self.engine)
    
    def ensure_schema(self):
        """Ensure database schema exists by creating all tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def upsert_emails(self, email_rows: Iterable[dict], batch_size: int = BATCH_SIZE_DEFAULT) -> int:
        """
        Insert many emails efficiently; skip duplicates by gmail_message_id.

        Uses PostgreSQL ON CONFLICT DO NOTHING on the unique key.
        Returns number of newly inserted rows.
        """
        inserted_total = 0
        buffer: List[dict] = []
        with self.get_session() as session:
            def flush_buffer() -> int:
                if not buffer:
                    return 0
                stmt = (
                    pg_insert(Email)
                    .values(buffer)
                    .on_conflict_do_nothing(index_elements=["gmail_message_id"])
                    .returning(Email.id)
                )
                result = session.execute(stmt)
                inserted_ids = list(result.scalars())
                session.commit()
                return len(inserted_ids)

            for row in email_rows:
                buffer.append(row)
                if len(buffer) >= batch_size:
                    inserted_total += flush_buffer()
                    buffer.clear()

            # flush remaining
            inserted_total += flush_buffer()

        return inserted_total
    
    def build_database_query(self, session: Session, rule):
        """
        Build a SQLAlchemy query based on rule conditions for database filtering.
        
        Args:
            session: Database session
            rule: Rule object with conditions and predicate
            
        Returns:
            SQLAlchemy query object
        """
        query = session.query(Email)
        
        if not rule.conditions:
            return query
        
        # Build conditions for each rule condition
        db_conditions = []
        
        for condition in rule.conditions:
            field = condition.field
            predicate = condition.predicate
            value = condition.value
            
            if field == FIELD_FROM:
                if predicate == PREDICATE_CONTAINS:
                    db_conditions.append(Email.from_address.ilike(f"%{value}%"))
                elif predicate == PREDICATE_DOES_NOT_CONTAIN:
                    db_conditions.append(~Email.from_address.ilike(f"%{value}%"))
                elif predicate == PREDICATE_EQUALS:
                    db_conditions.append(Email.from_address == value)
                elif predicate == PREDICATE_DOES_NOT_EQUAL:
                    db_conditions.append(Email.from_address != value)
                    
            elif field == FIELD_TO:
                if predicate == PREDICATE_CONTAINS:
                    db_conditions.append(Email.to_address.ilike(f"%{value}%"))
                elif predicate == PREDICATE_DOES_NOT_CONTAIN:
                    db_conditions.append(~Email.to_address.ilike(f"%{value}%"))
                elif predicate == PREDICATE_EQUALS:
                    db_conditions.append(Email.to_address == value)
                elif predicate == PREDICATE_DOES_NOT_EQUAL:
                    db_conditions.append(Email.to_address != value)
                    
            elif field == FIELD_SUBJECT:
                if predicate == PREDICATE_CONTAINS:
                    db_conditions.append(Email.subject.ilike(f"%{value}%"))
                elif predicate == PREDICATE_DOES_NOT_CONTAIN:
                    db_conditions.append(~Email.subject.ilike(f"%{value}%"))
                elif predicate == PREDICATE_EQUALS:
                    db_conditions.append(Email.subject == value)
                elif predicate == PREDICATE_DOES_NOT_EQUAL:
                    db_conditions.append(Email.subject != value)
                    
            elif field == FIELD_MESSAGE:
                if predicate == PREDICATE_CONTAINS:
                    db_conditions.append(Email.message.ilike(f"%{value}%"))
                elif predicate == PREDICATE_DOES_NOT_CONTAIN:
                    db_conditions.append(~Email.message.ilike(f"%{value}%"))
                elif predicate == PREDICATE_EQUALS:
                    db_conditions.append(Email.message == value)
                elif predicate == PREDICATE_DOES_NOT_EQUAL:
                    db_conditions.append(Email.message != value)
                    
            elif field == FIELD_RECEIVED:
                try:
                    num = float(value)
                    now = datetime.now(timezone.utc)
                    
                    if predicate == PREDICATE_LESS_THAN_DAYS:
                        cutoff_date = now - timedelta(days=num)
                        db_conditions.append(Email.received_at > cutoff_date)
                    elif predicate == PREDICATE_GREATER_THAN_DAYS:
                        cutoff_date = now - timedelta(days=num)
                        db_conditions.append(Email.received_at < cutoff_date)
                    elif predicate == PREDICATE_LESS_THAN_MONTHS:
                        cutoff_date = now - timedelta(days=num * DAYS_PER_MONTH)
                        db_conditions.append(Email.received_at > cutoff_date)
                    elif predicate == PREDICATE_GREATER_THAN_MONTHS:
                        cutoff_date = now - timedelta(days=num * DAYS_PER_MONTH)
                        db_conditions.append(Email.received_at < cutoff_date)
                except ValueError:
                    # If value can't be converted to float, skip this condition
                    continue
            else:
                raise ValueError(ERROR_INVALID_FIELD.format(field))
        
        # Apply conditions based on rule predicate
        if db_conditions:
            if rule.predicate == RULE_PREDICATE_ALL:
                query = query.filter(and_(*db_conditions))
            else:  # RULE_PREDICATE_ANY
                query = query.filter(or_(*db_conditions))
        
        # Print the raw SQL query
        return query
    
    def get_matching_emails(self, rule, offset: int = DEFAULT_OFFSET, limit: int = DEFAULT_LIMIT) -> List[Email]:
        """
        Get emails matching rule conditions from database with pagination.
        
        Args:
            rule: Rule to match against
            offset: Number of records to skip (for pagination)
            limit: Maximum messages to fetch per page
            
        Returns:
            List of Email objects matching the rule
        """
        with self.get_session() as session:
            query = self.build_database_query(session, rule)
            emails = query.offset(offset).limit(limit).all()
            return emails
    