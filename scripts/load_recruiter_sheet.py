from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.init_db import init_db
from db.session import SessionLocal
from main import app
from services.crm_client import CRMClient
from services.demo_import_service import import_recruiter_sheet, reset_demo_data
from services.sync_service import SyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset demo data, import the one-sheet recruiter CSV, and optionally run sync.")
    parser.add_argument("csv_path", help="Path to recruiter_demo_crm_sheet.csv")
    parser.add_argument("--no-reset", action="store_true", help="Do not clear existing demo data before import")
    parser.add_argument("--no-sync", action="store_true", help="Do not run sync after import")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    init_db()
    db = SessionLocal()
    try:
        if not args.no_reset:
            deleted = reset_demo_data(db)
            print("Reset complete:", deleted)

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            summary = import_recruiter_sheet(db, handle)
        print("Import complete:", summary)

        if not args.no_sync:
            test_client = app.test_client()
            original = CRMClient.fetch_incremental

            def fake_fetch_incremental(self, entity: str, updated_since):
                response = test_client.get(
                    f"/api/mock-crm/{entity}",
                    query_string={"limit": 200, "offset": 0},
                )
                if response.status_code != 200:
                    raise RuntimeError(f"Mock CRM fetch failed for {entity}: {response.status_code}")
                return response.get_json()["data"]

            CRMClient.fetch_incremental = fake_fetch_incremental  # type: ignore[assignment]
            try:
                sync_run = SyncService(db).run_sync(trigger_mode="csv_import")
                print(
                    "Sync complete:",
                    {
                        "sync_run_id": sync_run.id,
                        "status": sync_run.status,
                        "extracted": sync_run.extracted_count,
                        "inserted": sync_run.loaded_inserted_count,
                        "updated": sync_run.loaded_updated_count,
                        "rejected": sync_run.rejected_count,
                    },
                )
            finally:
                CRMClient.fetch_incremental = original  # type: ignore[assignment]
    finally:
        db.close()


if __name__ == "__main__":
    main()
