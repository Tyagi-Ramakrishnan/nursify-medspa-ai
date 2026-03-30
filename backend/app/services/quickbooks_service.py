"""
QuickBooks service — OAuth 2.0 and transaction sync using direct HTTP calls.
No third-party QB libraries needed — just httpx.
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


def sync_transactions(db: Session, days_back: int = 1) -> dict:
    token = get_active_token(db)
    if not token:
        return {"status": "error", "message": "No active QuickBooks connection"}

    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    base_url = QB_BASE.get(settings.QB_ENVIRONMENT, QB_BASE["sandbox"])
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/json",
    }

    created = 0
    skipped = 0

    with httpx.Client() as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": f"SELECT * FROM Invoice WHERE TxnDate >= '{since_date}'"},
            headers=headers,
        )
        resp.raise_for_status()
        invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])

    for inv in invoices:
        external_id = f"qb_invoice_{inv['Id']}"
        exists = db.query(Transaction).filter(
            and_(Transaction.external_id == external_id, Transaction.source == "quickbooks")
        ).first()
        if exists:
            skipped += 1
            continue
        db.add(Transaction(
            external_id=external_id,
            source="quickbooks",
            type="revenue",
            amount=inv.get("TotalAmt", 0),
            description=inv.get("CustomerRef", {}).get("name", ""),
            category=_extract_category(inv),
            status="settled" if inv.get("Balance", 1) == 0 else "pending",
            transaction_date=datetime.strptime(inv["TxnDate"], "%Y-%m-%d"),
            raw_data=inv,
        ))
        created += 1

    with httpx.Client() as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": f"SELECT * FROM Payment WHERE TxnDate >= '{since_date}'"},
            headers=headers,
        )
        resp.raise_for_status()
        payments = resp.json().get("QueryResponse", {}).get("Payment", [])

    for pmt in payments:
        external_id = f"qb_payment_{pmt['Id']}"
        exists = db.query(Transaction).filter(
            and_(Transaction.external_id == external_id, Transaction.source == "quickbooks")
        ).first()
        if exists:
            skipped += 1
            continue
        db.add(Transaction(
            external_id=external_id,
            source="quickbooks",
            type="revenue",
            amount=pmt.get("TotalAmt", 0),
            description=pmt.get("CustomerRef", {}).get("name", ""),
            status="settled",
            transaction_date=datetime.strptime(pmt["TxnDate"], "%Y-%m-%d"),
            raw_data=pmt,
        ))
        created += 1

    db.commit()
    return {"status": "ok", "created": created, "skipped": skipped}


def _extract_category(invoice: dict) -> str:
    for line in invoice.get("Line", []):
        desc = line.get("Description", "")
        if desc:
            return desc[:100]
    return "uncategorized"
