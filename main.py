from __future__ import annotations

import atexit

from flask import Flask, jsonify
from sqlalchemy import text

from api.dashboard import router as dashboard_router
from api.jobs import router as jobs_router
from api.mock_admin import router as mock_admin_router
from api.mock_crm import router as mock_crm_router
from api.reporting import router as reporting_router
from app.config import get_settings
from app.logging_utils import configure_logging
from db.init_db import init_db
from db.models import AppState, CRMCompany
from db.seed_data import seed_mock_crm
from db.session import SessionLocal
from jobs.scheduler import start_scheduler, stop_scheduler
from services.demo_import_service import get_boot_mode, set_boot_mode


settings = get_settings()
configure_logging(settings.log_level)

def bootstrap_data() -> None:
    init_db()
    db = SessionLocal()
    try:
        crm_count = db.query(CRMCompany).count()
        boot_mode = get_boot_mode(db)
        if boot_mode is None:
            if crm_count == 0:
                seed_mock_crm(db)
            set_boot_mode(db, "seeded_demo")
            db.commit()
        elif boot_mode == "seeded_demo" and not crm_count:
            seed_mock_crm(db)
    finally:
        db.close()


def create_app() -> Flask:
    bootstrap_data()
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(dashboard_router)
    app.register_blueprint(mock_admin_router)
    app.register_blueprint(mock_crm_router)
    app.register_blueprint(reporting_router)
    app.register_blueprint(jobs_router)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api-docs")
    def api_docs():
        """Redirect to dashboard API reference section."""
        from flask import redirect
        return redirect("/#api")

    start_scheduler()
    atexit.register(stop_scheduler)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=settings.app_host, port=settings.app_port, debug=settings.app_env == "development")
