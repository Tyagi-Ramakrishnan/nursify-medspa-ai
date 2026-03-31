"""
AI Categorization — uses Claude to suggest categories for uncategorized transactions,
then writes approved categories back to QuickBooks.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel
from typing import Optional
import httpx
import json
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.models import Transaction
from app.services.quickbooks_service import get_active_token
from app.core.config import settings

router = APIRouter()

# Med spa specific categories — Claude will pick from these
MEDSPA_CATEGORIES = [
    "Botox / Neurotoxin",
    "Dermal Fillers",
    "Laser Treatment",
    "Skincare / Facials",
    "Body Contouring",
    "Chemical Peel",
    "Microneedling",
    "PRP Treatment",
    "IV Therapy",
    "Medical Supplies",
    "Injectable Supplies",
    "Equipment Maintenance",
    "Staff / Payroll",
    "Marketing / Advertising",
    "Rent / Utilities",
    "Insurance",
    "Software / Technology",
    "Office Supplies",
    "Professional Development",
    "Consultation / Service Fee",
    "Retail Products",
    "Other Income",
    "Other Expense",
]


class ApproveCategory(BaseModel):
    transaction_id: str
    category: str
    write_to_quickbooks: bool = True


@router.get("/uncategorized")
def get_uncategorized(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return all transactions with no category or 'uncategorized' category."""
    txns = db.query(Transaction).filter(
        or_(
            Transaction.category == None,
            Transaction.category == "uncategorized",
            Transaction.category == "",
        )
    ).order_by(Transaction.transaction_date.desc()).limit(limit).all()

    return {
        "count": len(txns),
        "transactions": [
            {
                "id": str(t.id),
                "external_id": t.external_id,
                "description": t.description,
                "amount": float(t.amount),
                "type": t.type,
                "date": t.transaction_date.isoformat(),
                "status": t.status,
            }
            for t in txns
        ],
        "available_categories": MEDSPA_CATEGORIES,
    }


@router.post("/suggest")
def suggest_categories(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Call Claude AI to suggest categories for all uncategorized transactions.
    Returns suggestions without applying them — user reviews first.
    """
    txns = db.query(Transaction).filter(
        or_(
            Transaction.category == None,
            Transaction.category == "uncategorized",
            Transaction.category == "",
        )
    ).order_by(Transaction.transaction_date.desc()).limit(50).all()

    if not txns:
        return {"suggestions": []}

    # Build the prompt for Claude
    txn_list = "\n".join([
        f"- ID: {t.id} | {t.type.upper()} | ${t.amount} | {t.description or 'No description'} | {t.transaction_date.strftime('%Y-%m-%d')}"
        for t in txns
    ])

    prompt = f"""You are an AI assistant helping categorize financial transactions for a medical spa business.

Available categories:
{chr(10).join(f"- {c}" for c in MEDSPA_CATEGORIES)}

Transactions to categorize:
{txn_list}

For each transaction, suggest the most appropriate category from the list above.
Consider: revenue transactions are likely services provided, expense transactions are likely costs.
If unsure, use "Other Income" for revenue or "Other Expense" for expenses.

Respond with ONLY a JSON array, no other text:
[
  {{"id": "transaction-uuid", "category": "Category Name", "confidence": "high|medium|low", "reason": "brief reason"}},
  ...
]"""

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]

        # Parse JSON response
        clean = content.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        suggestions = json.loads(clean.strip())

        # Attach description and amount to each suggestion for the frontend
        txn_map = {str(t.id): t for t in txns}
        for s in suggestions:
            t = txn_map.get(s["id"])
            if t:
                s["description"] = t.description
                s["amount"] = float(t.amount)
                s["type"] = t.type
                s["date"] = t.transaction_date.isoformat()

        return {"suggestions": suggestions}

    except Exception as e:
        return {"error": str(e), "suggestions": []}


@router.post("/approve")
def approve_category(
    body: ApproveCategory,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Apply an approved category to a transaction and optionally write to QuickBooks."""
    txn = db.query(Transaction).filter(Transaction.id == body.transaction_id).first()
    if not txn:
        return {"error": "Transaction not found"}

    # Update in our database
    txn.category = body.category
    db.commit()

    # Write back to QuickBooks if requested
    qb_updated = False
    if body.write_to_quickbooks and txn.external_id:
        try:
            qb_updated = _update_qb_category(txn, body.category, db)
        except Exception as e:
            print(f"[categorize] QB write-back failed: {e}")

    return {
        "status": "approved",
        "transaction_id": body.transaction_id,
        "category": body.category,
        "quickbooks_updated": qb_updated,
    }


@router.post("/approve-all")
def approve_all(
    body: list,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Bulk approve multiple category suggestions at once."""
    results = []
    for item in body:
        txn = db.query(Transaction).filter(Transaction.id == item["id"]).first()
        if txn:
            txn.category = item["category"]
            results.append({"id": item["id"], "status": "approved"})
    db.commit()
    return {"approved": len(results), "results": results}


def _update_qb_category(txn: Transaction, category: str, db: Session) -> bool:
    """Write the category back to QuickBooks as a memo/account update."""
    token = get_active_token(db)
    if not token:
        return False

    base_url = (
        "https://sandbox-quickbooks.api.intuit.com"
        if settings.QB_ENVIRONMENT == "sandbox"
        else "https://quickbooks.api.intuit.com"
    )
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Extract QB object type and ID from external_id (e.g. qb_invoice_130)
    parts = txn.external_id.split("_")
    if len(parts) < 3:
        return False

    obj_type = parts[1].capitalize()  # invoice, payment, purchase -> Invoice, etc.
    obj_id = parts[2]

    # Fetch the current object
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{base_url}/v3/company/{token.realm_id}/{obj_type.lower()}/{obj_id}",
            headers=headers,
        )
        if not resp.ok:
            return False
        obj = resp.json().get(obj_type, {})

    # Add category as PrivateNote (memo)
    obj["PrivateNote"] = f"Category: {category}"
    sync_token = obj.get("SyncToken", "0")

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{base_url}/v3/company/{token.realm_id}/{obj_type.lower()}",
            headers=headers,
            json={obj_type: {**obj, "SyncToken": sync_token}},
        )
        return resp.ok
