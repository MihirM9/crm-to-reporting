from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from app.schemas import sync_summary_payload
from db.models import SyncRun
from db.session import SessionLocal
from services.sync_service import SyncService


router = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@router.post("/run-sync")
def run_sync():
    db = SessionLocal()
    try:
        sync_run = SyncService(db).run_sync(trigger_mode="manual")
        status_code = 202 if sync_run.status == "success" else 500
        return jsonify({"sync_run_id": sync_run.id, "status": sync_run.status, "message": sync_run.status_message or ""}), status_code
    finally:
        db.close()


@router.get("/latest-sync")
def latest_sync():
    db = SessionLocal()
    try:
        sync_run = db.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()))
        if not sync_run:
            return jsonify({"message": "No sync runs found"}), 404
        return jsonify(sync_summary_payload(sync_run))
    finally:
        db.close()
