import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from db.session import SessionLocal
from services.sync_service import SyncService


logger = logging.getLogger(__name__)
settings = get_settings()


scheduler = BackgroundScheduler()


def _scheduled_sync() -> None:
    db = SessionLocal()
    try:
        logger.info("Starting scheduled sync", extra={"event": "scheduled_sync_start", "context": {}})
        SyncService(db).run_sync(trigger_mode="scheduled")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(_scheduled_sync, "interval", seconds=settings.sync_interval_seconds, id="crm_reporting_sync", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
