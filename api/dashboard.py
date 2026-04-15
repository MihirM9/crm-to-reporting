from __future__ import annotations

from flask import Blueprint, render_template

from db.session import SessionLocal
from services.dashboard_service import get_dashboard_context


router = Blueprint("dashboard", __name__)


@router.get("/")
def dashboard():
    db = SessionLocal()
    try:
        context = get_dashboard_context(db)
        return render_template("dashboard.html", **context)
    finally:
        db.close()
