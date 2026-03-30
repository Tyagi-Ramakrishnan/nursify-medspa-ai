"""
Report service — aggregates the day's transactions and generates the daily report.
Called by the Celery beat job at 11 PM, or manually via the API.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.models import Transaction, DailyReport
from app.services.email_service import send_report_email


def generate_daily_report(db: Session, report_date: Optional[date] = None) -> DailyReport:
    """
    Aggregate all transactions for the given date and store as a DailyReport.
    Safe to call multiple times — updates existing report if already generated.
    """
    if report_date is None:
        report_date = date.today()

    day_start = datetime.combine(report_date, datetime.min.time())
    day_end = datetime.combine(report_date, datetime.max.time())

    # Pull all transactions for the day
    txns = db.query(Transaction).filter(
        and_(
            Transaction.transaction_date >= day_start,
            Transaction.transaction_date <= day_end,
        )
    ).all()

    # Aggregate totals
    total_revenue = sum(t.amount for t in txns if t.type == "revenue")
    total_expenses = sum(t.amount for t in txns if t.type == "expense")
    total_fees = sum(t.amount for t in txns if t.type == "fee")
    net_income = total_revenue - total_expenses - total_fees

    # Revenue by category
    category_breakdown: dict[str, Decimal] = {}
    for t in txns:
        if t.type == "revenue":
            cat = t.category or "uncategorized"
            category_breakdown[cat] = category_breakdown.get(cat, Decimal(0)) + t.amount

    # Revenue by source
    source_breakdown: dict[str, Decimal] = {}
    for t in txns:
        if t.type == "revenue":
            source_breakdown[t.source] = source_breakdown.get(t.source, Decimal(0)) + t.amount

    report_data = {
        "date": report_date.isoformat(),
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "total_fees": float(total_fees),
        "net_income": float(net_income),
        "transaction_count": len(txns),
        "category_breakdown": {k: float(v) for k, v in category_breakdown.items()},
        "source_breakdown": {k: float(v) for k, v in source_breakdown.items()},
        "pending_count": sum(1 for t in txns if t.status == "pending"),
    }

    # Upsert — update if report for this date already exists
    report = db.query(DailyReport).filter(
        DailyReport.report_date == day_start
    ).first()

    if not report:
        report = DailyReport(report_date=day_start)
        db.add(report)

    report.total_revenue = total_revenue
    report.total_expenses = total_expenses
    report.total_fees = total_fees
    report.net_income = net_income
    report.transaction_count = str(len(txns))
    report.report_data = report_data
    db.commit()
    db.refresh(report)

    return report


def get_last_7_days(db: Session) -> list[dict]:
    """Return daily report summaries for the last 7 days — used by the dashboard."""
    results = []
    for i in range(6, -1, -1):
        target_date = date.today() - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time())

        report = db.query(DailyReport).filter(
            DailyReport.report_date == day_start
        ).first()

        results.append({
            "date": target_date.isoformat(),
            "total_revenue": float(report.total_revenue) if report else 0,
            "net_income": float(report.net_income) if report else 0,
            "transaction_count": int(report.transaction_count) if report else 0,
        })

    return results
