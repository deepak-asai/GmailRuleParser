from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass

class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("gmail_message_id", name="uq_emails_gmail_message_id"),
        # GIN indexes for text-based searches (better for ILIKE '%pattern%' and equality)
        Index("ix_emails_subject_gin", "subject", postgresql_using="gin", postgresql_ops={"subject": "gin_trgm_ops"}),
        Index("ix_emails_from_address_gin", "from_address", postgresql_using="gin", postgresql_ops={"from_address": "gin_trgm_ops"}),
        Index("ix_emails_to_address_gin", "to_address", postgresql_using="gin", postgresql_ops={"to_address": "gin_trgm_ops"}),
        Index("ix_emails_message_gin", "message", postgresql_using="gin", postgresql_ops={"message": "gin_trgm_ops"}),
        # B-tree indexes for datetime searches
        Index("ix_emails_received_at", "received_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gmail_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    thread_id: Mapped[Optional[str]] = mapped_column(String(128))
    history_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    subject: Mapped[Optional[str]] = mapped_column(String(1024))
    from_address: Mapped[str] = mapped_column(String(1024), nullable=False)
    to_address: Mapped[str] = mapped_column(String(1024), nullable=False)

    message: Mapped[Optional[str]] = mapped_column(Text)
    label_ids: Mapped[Optional[list[str]]] = mapped_column(JSON)

    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )



