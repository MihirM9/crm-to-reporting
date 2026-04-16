"""Mock fund admin API — mimics a quarterly SS&C / Citco / Alter Domus feed.

Exposes `/api/mock-admin/positions` so reconciliation can pull over HTTP
(same shape as the CRM source), even though the seeded data also lives
in the local DB for convenience.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.schemas import paginated_response
from db.models import FundAdminRecord
from db.session import SessionLocal


router = Blueprint("mock_admin", __name__, url_prefix="/api/mock-admin")


def _serialize(row: FundAdminRecord) -> dict:
    payload: dict = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        payload[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return payload


@router.get("/positions")
def list_positions():
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)
    db = SessionLocal()
    try:
        rows = db.scalars(select(FundAdminRecord).order_by(FundAdminRecord.borrower_external_id)).all()
        page = rows[offset : offset + limit]
        return jsonify(paginated_response([_serialize(r) for r in page], limit, offset, len(rows)))
    finally:
        db.close()


@router.get("/positions/<borrower_external_id>")
def get_position(borrower_external_id: str):
    db = SessionLocal()
    try:
        row = db.scalar(select(FundAdminRecord).where(FundAdminRecord.borrower_external_id == borrower_external_id))
        if not row:
            return jsonify({"message": "Position not found"}), 404
        return jsonify(_serialize(row))
    finally:
        db.close()
