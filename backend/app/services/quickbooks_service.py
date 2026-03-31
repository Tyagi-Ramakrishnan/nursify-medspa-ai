import base64
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
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
    base_url = QB_BASE.get(settings.QB_ENVIRONMENT, QB_BASE["sandbox"])
    headers = {"Authorization": f"Bearer {token.access_token}", "Accept": "application/json"}
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/query",
            params={"query": query},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("QueryResponse", {})
        for v in data.values():
            if isinstance(v, list):
                return v
        return []


def _insert_txn(db: Session, external_id: str, source: str, **kwargs) -> bool:
    """Insert using ON CONFLICT DO NOTHING — never raises on duplicates."""
    stmt = insert(Transaction).values(
        id=uuid.uuid4(),
        external_id=external_id,
        source=source,
        created_at=datetime.utcnow(),
        currency="USD",
        **kwargs,
    ).on_conflict_do_nothing(index_elements=["external_id", "source"])
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def sync_transactions(db: Session, days_back: int = 90) -> dict:
    token = get_active_token(db)
    if not token:
        return {"status": "error", "message": "No active QuickBooks connection"}

    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    created = 0
    skipped = 0

    queries = [
        ("Invoice", f"SELECT * FROM Invoice MAXRESULTS 100"),
        ("Payment", f"SELECT * FROM Payment MAXRESULTS 100"),
        ("SalesReceipt", f"SELECT * FROM SalesReceipt MAXRESULTS 100"),
        ("Purchase", f"SELECT * FROM Purchase MAXRESULTS 100"),
        ("Bill", f"SELECT * FROM Bill MAXRESULTS 100"),
    ]

    for obj_type, query in queries:
        try:
            records = _qb_query(token, query)
            print(f"[sync] {obj_type}: {len(records)} records from QB")
        except Exception as e:
            print(f"[sync] {obj_type} query failed: {e}")
            continue

        for rec in records:
            try:
                ext_id = f"qb_{obj_type.lower()}_{rec['Id']}"
                txn_date = _parse_date(rec.get("TxnDate"))

                if obj_type in ("Invoice", "Payment", "SalesReceipt"):
                    inserted = _insert_txn(
                        db, ext_id, "quickbooks",
                        type="revenue",
                        amount=float(rec.get("TotalAmt", 0)),
                        description=rec.get("CustomerRef", {}).get("name", obj_type),
                        category=_extract_category(rec),
                        status="settled" if float(rec.get("Balance", 0)) == 0 else "pending",
                        transaction_date=txn_date,
                        raw_data=rec,
                    )
                else:
                    account = rec.get("AccountRef", {}).get("name", "") if obj_type == "Purchase" else ""
                    category = account if account and "uncategorized" not in account.lower() else None
                    description = (
                        rec.get("EntityRef", {}).get("name")
                        or rec.get("VendorRef", {}).get("name")
                        or obj_type
                    )
                    inserted = _insert_txn(
                        db, ext_id, "quickbooks",
                        type="expense",
                        amount=float(rec.get("TotalAmt", 0)),
                        description=description,
                        category=category,
                        status="settled",
                        transaction_date=txn_date,
                        raw_data=rec,
                    )

                if inserted:
                    created += 1
                else:
                    skipped += 1

            except Exception as e:
                print(f"[sync] Error inserting {ext_id}: {e}")
                skipped += 1

    print(f"[sync] Done — created: {created}, skipped: {skipped}")
    return {"status": "ok", "created": created, "skipped": skipped}


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime.utcnow()


def _extract_category(obj: dict) -> Optional[str]:
    for line in obj.get("Line", []):
        item = line.get("SalesItemLineDetail", {}).get("ItemRef", {}).get("name", "")
        if item:
            return item[:100]
        desc = line.get("Description", "")
        if desc:
            return desc[:100]
    return None
