from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.services.quickbooks_service import get_authorization_url, handle_callback, sync_transactions
from app.models.models import QuickBooksToken

router = APIRouter()


@router.get("/connect")
def connect_quickbooks():
    """Redirect to QuickBooks — no auth required, it's just a redirect."""
    url = get_authorization_url()
    return RedirectResponse(url)


@router.get("/callback")
def quickbooks_callback(
    request: Request,
    code: str,
    realmId: str,
    db: Session = Depends(get_db),
):
    """QuickBooks redirects here with the auth code."""
    handle_callback(auth_code=code, realm_id=realmId, db=db)
    return RedirectResponse("/?connected=true")


@router.get("/status")
def connection_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    token = db.query(QuickBooksToken).filter_by(is_active=True).first()
    if not token:
        return {"connected": False}
    return {
        "connected": True,
        "realm_id": token.realm_id,
        "expires_at": token.access_token_expires_at.isoformat(),
    }


@router.post("/sync")
def manual_sync(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = sync_transactions(db, days_back=7)
    return result


@router.get("/debug")
def debug_sync(db: Session = Depends(get_db)):
    """Temporary debug endpoint — shows raw QB query results."""
    from app.services.quickbooks_service import get_active_token, _qb_query
    token = get_active_token(db)
    if not token:
        return {"error": "No active token", "realm_id": None}
    
    try:
        invoices = _qb_query(token, "SELECT * FROM Invoice MAXRESULTS 5")
        purchases = _qb_query(token, "SELECT * FROM Purchase MAXRESULTS 5")
        bills = _qb_query(token, "SELECT * FROM Bill MAXRESULTS 5")
        receipts = _qb_query(token, "SELECT * FROM SalesReceipt MAXRESULTS 5")
        return {
            "realm_id": token.realm_id,
            "token_expires": token.access_token_expires_at.isoformat(),
            "invoices_found": len(invoices),
            "purchases_found": len(purchases),
            "bills_found": len(bills),
            "receipts_found": len(receipts),
            "sample_purchase": purchases[0] if purchases else None,
        }
    except Exception as e:
        return {"error": str(e), "realm_id": token.realm_id}
