from app.tasks.celery_app import celery_app
from app.db.database import SessionLocal
from app.services.quickbooks_service import sync_transactions
from app.services.report_service import generate_daily_report
from app.services.email_service import send_report_email


@celery_app.task(name="app.tasks.tasks.sync_quickbooks_task", bind=True, max_retries=3)
def sync_quickbooks_task(self):
    """Pull latest transactions from QuickBooks. Runs every 15 minutes."""
    db = SessionLocal()
    try:
        result = sync_transactions(db, days_back=1)
        print(f"[sync] {result}")
        return result
    except Exception as exc:
        print(f"[sync] Error: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(name="app.tasks.tasks.generate_report_task", bind=True, max_retries=2)
def generate_report_task(self):
    """Generate daily report and send email. Runs at 11 PM."""
    db = SessionLocal()
    try:
        report = generate_daily_report(db)
        if report.report_data:
            sent = send_report_email(report.report_data)
            report.email_sent = sent
            db.commit()
        return {"status": "ok", "date": str(report.report_date), "email_sent": report.email_sent}
    except Exception as exc:
        print(f"[report] Error: {exc}")
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()
