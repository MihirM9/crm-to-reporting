from db.init_db import init_db
from db.seed_data import seed_mock_crm
from db.session import SessionLocal
from db.models import SyncRun
from services.report_service import generate_reports


def test_generate_reports_writes_both_versions():
    init_db()
    db = SessionLocal()
    try:
        seed_mock_crm(db)
        sync_run = SyncRun(trigger_mode="test", status="success")
        db.add(sync_run)
        db.commit()
        db.refresh(sync_run)

        reports = generate_reports(db, sync_run)
        assert len(reports) == 4
        for report in reports:
            assert report.file_path
    finally:
        db.close()
