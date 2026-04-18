from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import Select, select

from app.schemas import paginated_response
from db.models import CRMCompany, CRMContact, CRMDeal, CRMMetric, CRMUpdate
from db.session import SessionLocal
from services.demo_import_service import import_recruiter_sheet_bytes, reset_demo_data
from services.sync_service import SyncService


router = Blueprint("mock_crm", __name__, url_prefix="/api/mock-crm")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _apply_incremental_filters(query: Select, model, updated_since: datetime | None):
    if updated_since:
        query = query.where(model.updated_at >= updated_since)
    return query.order_by(model.updated_at.asc(), model.id.asc())


def _serialize(model) -> dict:
    return {column.name: getattr(model, column.name).isoformat() if isinstance(getattr(model, column.name), datetime) else getattr(model, column.name) for column in model.__table__.columns}


def _list_records(model):
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)
    updated_since_value = request.args.get("updated_since")
    updated_since = datetime.fromisoformat(updated_since_value) if updated_since_value else None
    db = SessionLocal()
    try:
        query = _apply_incremental_filters(select(model), model, updated_since)
        rows = db.scalars(query).all()
        page = rows[offset : offset + limit]
        return jsonify(paginated_response([_serialize(row) for row in page], limit, offset, len(rows)))
    finally:
        db.close()


@router.get("/companies")
def list_companies():
    return _list_records(CRMCompany)


@router.get("/contacts")
def list_contacts():
    return _list_records(CRMContact)


@router.get("/deals")
def list_deals():
    return _list_records(CRMDeal)


@router.get("/metrics")
def list_metrics():
    return _list_records(CRMMetric)


@router.get("/updates")
def list_updates():
    return _list_records(CRMUpdate)


@router.patch("/companies/<external_id>")
def patch_company(external_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    db = SessionLocal()
    try:
        company = db.scalar(select(CRMCompany).where(CRMCompany.external_id == external_id))
        if not company:
            return jsonify({"message": "Company not found"}), 404
        for key, value in payload.items():
            if hasattr(company, key):
                setattr(company, key, value)
        company.updated_at = utcnow()
        db.add(company)
        db.commit()
        db.refresh(company)
        return jsonify(_serialize(company))
    finally:
        db.close()


@router.post("/reset-demo")
def reset_demo():
    db = SessionLocal()
    try:
        deleted = reset_demo_data(db)
        return jsonify({"status": "success", "message": "Demo data reset. Database is ready for custom CSV import.", "deleted": deleted})
    finally:
        db.close()


@router.post("/import-sheet")
def import_sheet():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"message": "Missing file upload. Send multipart/form-data with field name 'file'."}), 400

    reset_first = str(request.form.get("reset_first", "false")).lower() in {"1", "true", "yes"}
    run_sync = str(request.form.get("run_sync", "false")).lower() in {"1", "true", "yes"}

    db = SessionLocal()
    try:
        reset_summary = reset_demo_data(db) if reset_first else None
        summary = import_recruiter_sheet_bytes(db, uploaded.read())
        payload: dict[str, object] = {
            "status": "success",
            "message": "Recruiter sheet imported into mock CRM.",
            "reset_summary": reset_summary,
            "import_summary": {
                "total_rows": summary.total_rows,
                "imported_rows": summary.imported_rows,
                "skipped_rows": summary.skipped_rows,
                "counts_by_entity": summary.counts_by_entity,
            },
        }
        if run_sync:
            sync_run = SyncService(db).run_sync(trigger_mode="csv_import")
            payload["sync_run"] = {
                "sync_run_id": sync_run.id,
                "status": sync_run.status,
                "extracted_count": sync_run.extracted_count,
                "loaded_inserted_count": sync_run.loaded_inserted_count,
                "loaded_updated_count": sync_run.loaded_updated_count,
                "rejected_count": sync_run.rejected_count,
                "message": sync_run.status_message or "",
            }
        return jsonify(payload)
    finally:
        db.close()
