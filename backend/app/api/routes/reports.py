from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.services.report_service import generate_daily_report, get_last_7_days
from app.services.email_service import send_report_email
from app.models.models import DailyReport

router = APIRouter()


@router.get("/today")
def today_report(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get or generate today's report. Used by the dashboard hero card."""
    report = generate_daily_report(db, report_date=date.today())
    return report.report_data


@router.get("/last-7-days")
def last_7_days(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return daily summaries for the last 7 days. Used by the dashboard chart."""
    return get_last_7_days(db)


@router.post("/generate")
def trigger_report(
    background_tasks: BackgroundTasks,
    report_date: Optional[date] = Query(default=None),
    send_email: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Manually trigger report generation for any date."""
    report = generate_daily_report(db, report_date=report_date)

    if send_email and report.report_data:
        background_tasks.add_task(send_report_email, report.report_data)

    return {
        "status": "generated",
        "date": str(report.report_date),
        "net_income": float(report.net_income),
        "email_queued": send_email,
    }


@router.get("/history")
def report_history(
    limit: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Last N daily reports — for future history page."""
    reports = (
        db.query(DailyReport)
        .order_by(DailyReport.report_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "date": r.report_date.date().isoformat(),
            "total_revenue": float(r.total_revenue),
            "net_income": float(r.net_income),
            "transaction_count": int(r.transaction_count),
            "email_sent": r.email_sent,
        }
        for r in reports
    ]
