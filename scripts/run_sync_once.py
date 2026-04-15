from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db.init_db import init_db
from db.seed_data import seed_mock_crm
from db.session import SessionLocal
from jobs.scheduler import stop_scheduler
from main import app
from services.crm_client import CRMClient
from services.sync_service import SyncService


def main() -> None:
    init_db()
    db = SessionLocal()
    client = app.test_client()

    def local_fetch_incremental(self, entity: str, updated_since):
        query_string = {"limit": 50, "offset": 0}
        if updated_since:
            query_string["updated_since"] = updated_since.isoformat()
        response = client.get(f"/api/mock-crm/{entity}", query_string=query_string)
        if response.status_code != 200:
            raise RuntimeError(f"Mock CRM request failed for {entity}: {response.status_code}")
        return response.get_json()["data"]

    try:
        seed_mock_crm(db)
        CRMClient.fetch_incremental = local_fetch_incremental
        sync_run = SyncService(db).run_sync(trigger_mode="manual")
        print(f"Completed sync run {sync_run.id} with status={sync_run.status}")
    finally:
        db.close()
        stop_scheduler()


if __name__ == "__main__":
    main()
