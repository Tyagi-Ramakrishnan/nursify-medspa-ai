"""
QuickBooks service — OAuth 2.0 and transaction sync using direct HTTP calls.
"""

import base64
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.core.config import settings
from app.models.models import Transaction, QuickBooksToken

INTUIT_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES = "com.intuit.quickbooks.accounting"

QB_BASE = {
    "sandbox": "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}


def _basic_auth_header() -> str:
    creds = f"{settings.QB_CLIENT_ID}:{settings.QB_CLIENT_SECRET}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


def get_authorization_url() -> str:
    params = {
        "client_id": settings.QB_CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": settings.QB_REDIRECT_URI,
        "response_type": "code",
        "state": "nursify_medspa",
    }
    return f"{INTUIT_AUTH_URL}?{urlencode(params)}"


def handle_callback(auth_code: str, realm_id: str, db: Session) -> QuickBooksToken:
    with httpx.Client() as client:
        resp = client.post(
            INTUIT_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": settings.QB_REDIRECT_URI,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

    token = db.query(QuickBooksToken).filter_by(realm_id=realm_id).first()
    if not token:
        token = QuickBooksToken(realm_id=realm_id)
        db.add(token)

    token.access_token = tokens["access_token"]
    token.refresh_token = tokens["refresh_token"]
    token.access_token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    token.refresh_token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("x_refresh_token_expires_in", 8640000))
    token.is_active = True
    db.commit()
    db.refresh(token)
    return token


def refresh_access_token(token: QuickBooksToken, db: Session) -> QuickBooksToken:
    with httpx.Client() as client:
        resp = client.post(
            INTUIT_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

    token.access_token = tokens["access_token"]
    token.refresh_token = tokens.get("refresh_token", token.refresh_token)
    token.access_token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    db.commit()
    return token


def get_active_token(db: Session) -> Optional[QuickBooksToken]:
    token = db.query(QuickBooksToken).filter_by(is_active=True).first()
    if not token:
        return None
    if token.access_token_expires_at < datetime.utcnow() + timedelta(minutes=5):
        token = refresh_access_token(token, db)
    return token


def _qb_query(token: QuickBooksToken, query: str) -> list:
    """Run a QuickBooks query and return the results."""
    base_url = QB_BASE.get(settings.QB_ENVIRONMENT, QB_BASE["sandbox"])
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": query},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("QueryResponse", {})
        # Return first non-empty list found
        for v in data.values():
            if isinstance(v, list):
                return v
        return []


def _upsert_transaction(db: Session, external_id: str, **kwargs) -> bool:
    """Insert transaction if it doesn't exist. Returns True if created."""
    exists = db.query(Transaction).filter(
        and_(
            Transaction.external_id == external_id,
            Transaction.source == "quickbooks",
        )
    ).first()
    if exists:
        return False
    db.add(Transaction(external_id=external_id, source="quickbooks", **kwargs))
    return True


def sync_transactions(db: Session, days_back: int = 90) -> dict:
    """
    Pull all transaction types from QuickBooks.
    Covers: Invoice, Payment, Purchase, Bill, SalesReceipt
    """
    token = get_active_token(db)
    if not token:
        return {"status": "error", "message": "No active QuickBooks connection"}

    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    created = 0
    skipped = 0

    # --- Invoices (revenue) ---
    for inv in _qb_query(token, f"SELECT * FROM Invoice WHERE TxnDate >= '{since_date}'"):
        txn_date = _parse_date(inv.get("TxnDate"))
        if _upsert_transaction(
            db,
            external_id=f"qb_invoice_{inv['Id']}",
            type="revenue",
            amount=inv.get("TotalAmt", 0),
            description=inv.get("CustomerRef", {}).get("name", "Invoice"),
            category=_extract_invoice_category(inv),
            status="settled" if inv.get("Balance", 1) == 0 else "pending",
            transaction_date=txn_date,
            raw_data=inv,
        ):
            created += 1
        else:
            skipped += 1

    # --- Payments (revenue) ---
    for pmt in _qb_query(token, f"SELECT * FROM Payment WHERE TxnDate >= '{since_date}'"):
        txn_date = _parse_date(pmt.get("TxnDate"))
        if _upsert_transaction(
            db,
            external_id=f"qb_payment_{pmt['Id']}",
            type="revenue",
            amount=pmt.get("TotalAmt", 0),
            description=pmt.get("CustomerRef", {}).get("name", "Payment"),
            status="settled",
            transaction_date=txn_date,
            raw_data=pmt,
        ):
            created += 1
        else:
            skipped += 1

    # --- Sales Receipts (revenue) ---
    for sr in _qb_query(token, f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{since_date}'"):
        txn_date = _parse_date(sr.get("TxnDate"))
        if _upsert_transaction(
            db,
            external_id=f"qb_salesreceipt_{sr['Id']}",
            type="revenue",
            amount=sr.get("TotalAmt", 0),
            description=sr.get("CustomerRef", {}).get("name", "Sales Receipt"),
            category=_extract_invoice_category(sr),
            status="settled",
            transaction_date=txn_date,
            raw_data=sr,
        ):
            created += 1
        else:
            skipped += 1

    # --- Purchases / Expenses ---
    for pur in _qb_query(token, f"SELECT * FROM Purchase WHERE TxnDate >= '{since_date}'"):
        txn_date = _parse_date(pur.get("TxnDate"))
        account_ref = pur.get("AccountRef", {}).get("name", "")
        category = account_ref if account_ref and "uncategorized" not in account_ref.lower() else None
        if _upsert_transaction(
            db,
            external_id=f"qb_purchase_{pur['Id']}",
            type="expense",
            amount=pur.get("TotalAmt", 0),
            description=pur.get("EntityRef", {}).get("name") or pur.get("PrivateNote", "Expense"),
            category=category,
            status="settled",
            transaction_date=txn_date,
            raw_data=pur,
        ):
            created += 1
        else:
            skipped += 1

    # --- Bills (expenses) ---
    for bill in _qb_query(token, f"SELECT * FROM Bill WHERE TxnDate >= '{since_date}'"):
        txn_date = _parse_date(bill.get("TxnDate"))
        if _upsert_transaction(
            db,
            external_id=f"qb_bill_{bill['Id']}",
            type="expense",
            amount=bill.get("TotalAmt", 0),
            description=bill.get("VendorRef", {}).get("name", "Bill"),
            category=_extract_bill_category(bill),
            status="pending" if float(bill.get("Balance", 0)) > 0 else "settled",
            transaction_date=txn_date,
            raw_data=bill,
        ):
            created += 1
        else:
            skipped += 1

    db.commit()
    return {"status": "ok", "created": created, "skipped": skipped}


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime.utcnow()


def _extract_invoice_category(obj: dict) -> Optional[str]:
    for line in obj.get("Line", []):
        detail = line.get("SalesItemLineDetail", {})
        item = detail.get("ItemRef", {}).get("name", "")
        if item:
            return item[:100]
        desc = line.get("Description", "")
        if desc:
            return desc[:100]
    return None


def _extract_bill_category(bill: dict) -> Optional[str]:
    for line in bill.get("Line", []):
        detail = line.get("AccountBasedExpenseLineDetail", {})
        account = detail.get("AccountRef", {}).get("name", "")
        if account and "uncategorized" not in account.lower():
            return account[:100]
    return None
