from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import Select, select

from app.schemas import paginated_response
from db.models import CRMCompany, CRMContact, CRMDeal, CRMMetric, CRMUpdate
from db.session import SessionLocal


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
