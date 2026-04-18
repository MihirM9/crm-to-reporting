from pathlib import Path

from sqlalchemy import select

from db.init_db import init_db
from db.models import CRMCompany, ReportingCompany
from db.session import SessionLocal
from main import app
from services.crm_client import CRMClient
from services.demo_import_service import import_recruiter_sheet, reset_demo_data
from services.sync_service import SyncService


def test_recruiter_sheet_import_and_sync(monkeypatch):
    init_db()
    db = SessionLocal()
    test_client = app.test_client()
    csv_path = Path("examples/recruiter_demo_crm_sheet.csv")

    def fake_fetch_incremental(self, entity: str, updated_since):
        response = test_client.get(f"/api/mock-crm/{entity}", query_string={"limit": 200, "offset": 0})
        assert response.status_code == 200
        return response.get_json()["data"]

    monkeypatch.setattr(CRMClient, "fetch_incremental", fake_fetch_incremental)

    try:
        reset_demo_data(db)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            summary = import_recruiter_sheet(db, handle)

        assert summary.imported_rows >= 10
        assert summary.counts_by_entity["company"] >= 4

        sync_run = SyncService(db).run_sync(trigger_mode="test_import")
        assert sync_run.status == "success"
        assert sync_run.rejected_count >= 1

        companies = db.scalars(select(CRMCompany)).all()
        reporting = db.scalars(select(ReportingCompany)).all()
        assert len(companies) >= 4
        assert len(reporting) >= 1
    finally:
        db.close()
