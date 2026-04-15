from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, send_file
from sqlalchemy import select

from db.models import DealPipeline, GeneratedReport, RejectedRecord, ReportingCompany, ReportingMetric, ReportingUpdate, SyncRun
from db.session import SessionLocal


router = Blueprint("reporting", __name__, url_prefix="/api/reporting")


def _serialize(model) -> dict:
    payload = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        payload[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return payload


@router.get("/companies")
def reporting_companies():
    db = SessionLocal()
    try:
        rows = db.scalars(select(ReportingCompany).order_by(ReportingCompany.company_name)).all()
        return jsonify([_serialize(row) for row in rows])
    finally:
        db.close()


@router.get("/deal-pipeline")
def reporting_deals():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(DealPipeline).order_by(DealPipeline.updated_at.desc())).all()])
    finally:
        db.close()


@router.get("/metrics")
def reporting_metrics():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(ReportingMetric).order_by(ReportingMetric.company_external_id)).all()])
    finally:
        db.close()


@router.get("/updates")
def reporting_updates():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(ReportingUpdate).order_by(ReportingUpdate.updated_at.desc())).all()])
    finally:
        db.close()


@router.get("/sync-runs")
def sync_runs():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc())).all()])
    finally:
        db.close()


@router.get("/rejected-records")
def rejected_records():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(RejectedRecord).order_by(RejectedRecord.created_at.desc())).all()])
    finally:
        db.close()


@router.get("/reports")
def generated_reports():
    db = SessionLocal()
    try:
        return jsonify([_serialize(row) for row in db.scalars(select(GeneratedReport).order_by(GeneratedReport.created_at.desc())).all()])
    finally:
        db.close()


@router.get("/reports/<int:report_id>/download")
def download_report(report_id: int):
    db = SessionLocal()
    try:
        report = db.scalar(select(GeneratedReport).where(GeneratedReport.id == report_id))
        if not report:
            return jsonify({"message": "Report not found"}), 404
        path = Path(report.file_path)
        if not path.exists():
            return jsonify({"message": "Report file missing on disk"}), 404
        return send_file(path, mimetype="text/html" if path.suffix == ".html" else "text/markdown", download_name=path.name)
    finally:
        db.close()
