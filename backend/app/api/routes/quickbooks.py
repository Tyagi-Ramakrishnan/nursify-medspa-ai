from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.services.quickbooks_service import get_authorization_url, handle_callback, sync_transactions
from app.models.models import QuickBooksToken

router = APIRouter()


@router.get("/connect")
def connect_quickbooks(user: dict = Depends(get_current_user)):
    """Step 1: Redirect the user to QuickBooks to authorize the connection."""
    url = get_authorization_url()
    return RedirectResponse(url)


@router.get("/callback")
def quickbooks_callback(
    request: Request,
    code: str,
    realmId: str,
    db: Session = Depends(get_db),
):
    """Step 2: QuickBooks redirects here with the auth code. Exchange it for tokens."""
    handle_callback(auth_code=code, realm_id=realmId, db=db)
    return {"status": "connected", "realm_id": realmId}


@router.get("/status")
def connection_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Check whether a QuickBooks connection is active."""
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
    """Manually trigger a QuickBooks sync — useful for testing."""
    result = sync_transactions(db, days_back=7)
    return result
