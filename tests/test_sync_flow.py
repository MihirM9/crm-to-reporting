from sqlalchemy import select

from db.init_db import init_db
from db.models import GeneratedReport, SyncRun
from db.seed_data import seed_mock_crm
from db.session import SessionLocal
from main import app
from services.crm_client import CRMClient
from services.sync_service import SyncService


def test_sync_flow_creates_run_and_reports(monkeypatch):
    init_db()
    db = SessionLocal()
    seed_mock_crm(db)
    client = app.test_client()

    def fake_fetch_incremental(self, entity: str, updated_since):
        response = client.get(f"/api/mock-crm/{entity}", query_string={"limit": 50, "offset": 0})
        assert response.status_code == 200
        return response.get_json()["data"]

    monkeypatch.setattr(CRMClient, "fetch_incremental", fake_fetch_incremental)

    try:
        sync_run = SyncService(db).run_sync(trigger_mode="test")
        assert sync_run.status == "success"
        assert sync_run.rejected_count >= 1

        latest = db.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()))
        assert latest is not None
        assert latest.status == "success"

        reports = db.scalars(select(GeneratedReport)).all()
        assert len(reports) >= 4
    finally:
        db.close()
