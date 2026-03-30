"""
QuickBooks service — handles OAuth flow and transaction sync.

OAuth flow:
  1. User hits /api/v1/quickbooks/connect  → redirected to Intuit login
  2. Intuit redirects back to /api/v1/quickbooks/callback with auth code
  3. We exchange code for access + refresh tokens, store in DB
  4. Celery job calls sync_transactions() every 15 minutes
"""

from datetime import datetime, timedelta
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from app.core.config import settings
from app.models.models import Transaction, QuickBooksToken


def get_auth_client() -> AuthClient:
    return AuthClient(
        client_id=settings.QB_CLIENT_ID,
        client_secret=settings.QB_CLIENT_SECRET,
        redirect_uri=settings.QB_REDIRECT_URI,
        environment=settings.QB_ENVIRONMENT,
    )


def get_authorization_url() -> str:
    """Step 1: Generate the URL to send the user to Intuit for login."""
    auth_client = get_auth_client()
    return auth_client.get_authorization_url([Scopes.ACCOUNTING])


def handle_callback(auth_code: str, realm_id: str, db: Session) -> QuickBooksToken:
    """Step 2: Exchange auth code for tokens and store them."""
    auth_client = get_auth_client()
    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    token = db.query(QuickBooksToken).filter_by(realm_id=realm_id).first()
    if not token:
        token = QuickBooksToken(realm_id=realm_id)
        db.add(token)

    token.access_token = auth_client.access_token
    token.refresh_token = auth_client.refresh_token
    token.access_token_expires_at = datetime.utcnow() + timedelta(seconds=3600)
    token.refresh_token_expires_at = datetime.utcnow() + timedelta(days=100)
    token.is_active = True
    db.commit()
    db.refresh(token)
    return token


def refresh_access_token(token: QuickBooksToken, db: Session) -> QuickBooksToken:
    """Refresh the access token using the refresh token before it expires."""
    auth_client = get_auth_client()
    auth_client.refresh(refresh_token=token.refresh_token)

    token.access_token = auth_client.access_token
    token.refresh_token = auth_client.refresh_token
    token.access_token_expires_at = datetime.utcnow() + timedelta(seconds=3600)
    db.commit()
    return token


def get_active_token(db: Session) -> Optional[QuickBooksToken]:
    """Get the active QB token, refreshing if needed."""
    token = db.query(QuickBooksToken).filter_by(is_active=True).first()
    if not token:
        return None

    # Refresh if expiring within 5 minutes
    if token.access_token_expires_at < datetime.utcnow() + timedelta(minutes=5):
        token = refresh_access_token(token, db)

    return token


def sync_transactions(db: Session, days_back: int = 1) -> dict:
    """
    Pull invoices and payments from QuickBooks and store them.
    Uses external_id + source as the deduplication key — safe to run repeatedly.
    """
    token = get_active_token(db)
    if not token:
        return {"status": "error", "message": "No active QuickBooks connection"}

    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    base_url = (
        "https://sandbox-quickbooks.api.intuit.com"
        if settings.QB_ENVIRONMENT == "sandbox"
        else "https://quickbooks.api.intuit.com"
    )

    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/json",
    }

    created = 0
    skipped = 0

    # Fetch invoices (booked revenue)
    invoice_query = f"SELECT * FROM Invoice WHERE TxnDate >= '{since_date}'"
    with httpx.Client() as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": invoice_query},
            headers=headers,
        )
        resp.raise_for_status()
        invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])

    for inv in invoices:
        external_id = f"qb_invoice_{inv['Id']}"
        exists = db.query(Transaction).filter(
            and_(
                Transaction.external_id == external_id,
                Transaction.source == "quickbooks",
            )
        ).first()

        if exists:
            skipped += 1
            continue

        txn = Transaction(
            external_id=external_id,
            source="quickbooks",
            type="revenue",
            amount=inv.get("TotalAmt", 0),
            description=inv.get("CustomerRef", {}).get("name", ""),
            category=_extract_category(inv),
            status="settled" if inv.get("Balance", 1) == 0 else "pending",
            transaction_date=datetime.strptime(inv["TxnDate"], "%Y-%m-%d"),
            raw_data=inv,
        )
        db.add(txn)
        created += 1

    # Fetch payments
    payment_query = f"SELECT * FROM Payment WHERE TxnDate >= '{since_date}'"
    with httpx.Client() as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": payment_query},
            headers=headers,
        )
        resp.raise_for_status()
        payments = resp.json().get("QueryResponse", {}).get("Payment", [])

    for pmt in payments:
        external_id = f"qb_payment_{pmt['Id']}"
        exists = db.query(Transaction).filter(
            and_(
                Transaction.external_id == external_id,
                Transaction.source == "quickbooks",
            )
        ).first()

        if exists:
            skipped += 1
            continue

        txn = Transaction(
            external_id=external_id,
            source="quickbooks",
            type="revenue",
            amount=pmt.get("TotalAmt", 0),
            description=pmt.get("CustomerRef", {}).get("name", ""),
            status="settled",
            transaction_date=datetime.strptime(pmt["TxnDate"], "%Y-%m-%d"),
            raw_data=pmt,
        )
        db.add(txn)
        created += 1

    db.commit()
    return {"status": "ok", "created": created, "skipped": skipped}


def _extract_category(invoice: dict) -> str:
    """Pull the first line item's description as the service category."""
    lines = invoice.get("Line", [])
    for line in lines:
        desc = line.get("Description", "")
        if desc:
            return desc[:100]
    return "uncategorized"
