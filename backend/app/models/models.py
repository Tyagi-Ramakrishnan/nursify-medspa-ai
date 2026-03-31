import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, JSON, Text, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("external_id", "source", name="ix_transactions_external_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), nullable=False, index=True)
    source = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    status = Column(String(50), default="settled", nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_data = Column(JSON, nullable=True)


class QuickBooksToken(Base):
    __tablename__ = "quickbooks_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    realm_id = Column(String(100), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    access_token_expires_at = Column(DateTime, nullable=False)
    refresh_token_expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_date = Column(DateTime, nullable=False, unique=True)
    total_revenue = Column(Numeric(12, 2), default=0)
    total_expenses = Column(Numeric(12, 2), default=0)
    total_fees = Column(Numeric(12, 2), default=0)
    net_income = Column(Numeric(12, 2), default=0)
    transaction_count = Column(String(10), default="0")
    report_data = Column(JSON, nullable=True)
    email_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
