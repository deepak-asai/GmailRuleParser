from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Iterable, List

from sqlalchemy import or_, and_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import Base, Email
from .config import get_settings
from .db import create_engine_for_url


class DatabaseService:
    """Service class for handling all database operations"""
    
    def __init__(self):
        """Initialize database service with engine"""
        settings = get_settings()
        self.engine = create_engine_for_url(settings.database_url)
    
    def ensure_schema(self) -> None:
        """Ensure database schema exists"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return Session(self.engine)
    
    def upsert_emails(self, email_rows: Iterable[dict], batch_size: int = 1000) -> int:
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
    
    def get_matching_emails(self, rule, offset: int = 0, limit: int = 20) -> List[Email]:
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
    
# Backward compatibility functions
def ensure_schema(engine: Engine) -> None:
    """Ensure database schema exists (backward compatibility)"""
    Base.metadata.create_all(bind=engine)


def upsert_emails(email_rows: Iterable[dict], batch_size: int = 1000) -> int:
    """
    Insert many emails efficiently; skip duplicates by gmail_message_id (backward compatibility).

    Uses PostgreSQL ON CONFLICT DO NOTHING on the unique key.
    Returns number of newly inserted rows.
    """
    db_service = DatabaseService()
    return db_service.upsert_emails(email_rows, batch_size)
