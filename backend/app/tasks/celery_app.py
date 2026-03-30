"""
Celery tasks — scheduled jobs that run in the background.

Schedule:
  - sync_quickbooks_task   every 15 minutes (continuous ingest)
  - generate_report_task   daily at 11 PM    (end-of-day report + email)
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "nursify",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.beat_schedule = {
    "sync-quickbooks-every-15-minutes": {
        "task": "app.tasks.tasks.sync_quickbooks_task",
        "schedule": crontab(minute="*/15"),
    },
    "generate-daily-report-11pm": {
        "task": "app.tasks.tasks.generate_report_task",
        "schedule": crontab(hour=23, minute=0),
    },
}

celery_app.conf.timezone = "America/New_York"
