from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.models import Transaction

router = APIRouter()


@router.get("/")
def list_transactions(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    source: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=500, le=5000),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if start_date is None:
        start_date = date.today() - timedelta(days=7)
    if end_date is None:
        end_date = date.today()

    query = db.query(Transaction).filter(
        and_(
            Transaction.transaction_date >= datetime.combine(start_date, datetime.min.time()),
            Transaction.transaction_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )

    if source:
        query = query.filter(Transaction.source == source)
    if type:
        query = query.filter(Transaction.type == type)

    total = query.count()
    txns = query.order_by(Transaction.transaction_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "transactions": [
            {
                "id": str(t.id),
                "external_id": t.external_id,
                "source": t.source,
                "type": t.type,
                "amount": float(t.amount),
                "description": t.description,
                "category": t.category,
                "status": t.status,
                "date": t.transaction_date.isoformat(),
            }
            for t in txns
        ],
    }
