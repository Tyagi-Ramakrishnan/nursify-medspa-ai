"""Initial schema — transactions, quickbooks_tokens, daily_reports

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), default="settled"),
        sa.Column("transaction_date", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("raw_data", postgresql.JSON, nullable=True),
    )
    # Composite unique index — the deduplication key
    op.create_index(
        "ix_transactions_external_source",
        "transactions",
        ["external_id", "source"],
        unique=True,
    )

    op.create_table(
        "quickbooks_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("realm_id", sa.String(100), unique=True, nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime, nullable=False),
        sa.Column("refresh_token_expires_at", sa.DateTime, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "daily_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_date", sa.DateTime, nullable=False, unique=True),
        sa.Column("total_revenue", sa.Numeric(12, 2), default=0),
        sa.Column("total_expenses", sa.Numeric(12, 2), default=0),
        sa.Column("total_fees", sa.Numeric(12, 2), default=0),
        sa.Column("net_income", sa.Numeric(12, 2), default=0),
        sa.Column("transaction_count", sa.String(10), default="0"),
        sa.Column("report_data", postgresql.JSON, nullable=True),
        sa.Column("email_sent", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("daily_reports")
    op.drop_table("quickbooks_tokens")
    op.drop_index("ix_transactions_external_source", table_name="transactions")
    op.drop_table("transactions")
