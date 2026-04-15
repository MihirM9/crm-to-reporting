from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db.init_db import init_db
from db.seed_data import seed_mock_crm
from db.session import SessionLocal


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_mock_crm(db)
        print("Seeded mock CRM data.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
