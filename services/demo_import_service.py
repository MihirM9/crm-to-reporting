from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, TextIO

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import (
    AppState,
    CRMCompany,
    CRMContact,
    CRMDeal,
    CRMMetric,
    CRMUpdate,
    CovenantBreach,
    DealPipeline,
    FacilityCovenant,
    FundAdminRecord,
    GeneratedReport,
    ReconciliationBreak,
    RejectedRecord,
    ReportingCompany,
    ReportingMetric,
    ReportingUpdate,
    SyncRun,
)


RECRUITER_IMPORT_MODE = "custom_import"


@dataclass
class ImportSummary:
    total_rows: int
    imported_rows: int
    skipped_rows: int
    counts_by_entity: dict[str, int]


def set_boot_mode(db: Session, value: str) -> None:
    db.merge(AppState(key="boot_mode", value=value))
    db.flush()


def get_boot_mode(db: Session) -> str | None:
    state = db.get(AppState, "boot_mode")
    return state.value if state else None


def reset_demo_data(db: Session) -> dict[str, int]:
    report_paths = [Path(path) for path in db.scalars(select(GeneratedReport.file_path)).all()]
    deleted: dict[str, int] = {}
    models = [
        CovenantBreach,
        ReconciliationBreak,
        FacilityCovenant,
        FundAdminRecord,
        GeneratedReport,
        RejectedRecord,
        SyncRun,
        ReportingUpdate,
        ReportingMetric,
        ReportingCompany,
        DealPipeline,
        CRMUpdate,
        CRMMetric,
        CRMDeal,
        CRMContact,
        CRMCompany,
    ]
    for model in models:
        result = db.execute(delete(model))
        deleted[model.__tablename__] = result.rowcount or 0
    set_boot_mode(db, RECRUITER_IMPORT_MODE)
    db.commit()

    removed_files = 0
    for path in report_paths:
        if path.exists():
            path.unlink()
            removed_files += 1
    deleted["report_files_removed"] = removed_files
    return deleted


def import_recruiter_sheet(db: Session, file_obj: TextIO) -> ImportSummary:
    reader = csv.DictReader(file_obj)
    counts = {"company": 0, "contact": 0, "deal": 0, "metric": 0, "update": 0}
    total_rows = 0
    imported_rows = 0
    skipped_rows = 0

    for raw_row in reader:
        if raw_row is None:
            continue
        row = {key: _clean(value) for key, value in raw_row.items()}
        if not any(row.values()):
            continue
        total_rows += 1
        entity_type = (row.get("entity_type") or "").lower()
        model = _build_model(entity_type, row)
        if model is None:
            skipped_rows += 1
            continue
        db.add(model)
        counts[entity_type] += 1
        imported_rows += 1

    set_boot_mode(db, RECRUITER_IMPORT_MODE)
    db.commit()
    return ImportSummary(
        total_rows=total_rows,
        imported_rows=imported_rows,
        skipped_rows=skipped_rows,
        counts_by_entity=counts,
    )


def import_recruiter_sheet_bytes(db: Session, payload: bytes) -> ImportSummary:
    text = payload.decode("utf-8-sig")
    return import_recruiter_sheet(db, StringIO(text))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _float_or_raw(value: str | None) -> float | str | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return value


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None


def _datetime_or_none(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _build_model(entity_type: str, row: dict[str, Any]):
    updated_at = _datetime_or_none(row.get("updated_at"))
    common_source = row.get("source_system") or "uploaded_csv"
    if entity_type == "company":
        return CRMCompany(
            external_id=row.get("external_id"),
            name=row.get("name_or_title"),
            owner=row.get("owner"),
            stage=row.get("stage_or_type"),
            reporting_period=row.get("reporting_period"),
            valuation=_float_or_none(row.get("amount_or_valuation")),
            updated_at=updated_at,
            source_system=common_source,
            status="active",
        )
    if entity_type == "contact":
        return CRMContact(
            external_id=row.get("external_id"),
            company_external_id=row.get("linked_company_external_id"),
            full_name=row.get("name_or_title"),
            email=row.get("email"),
            owner=row.get("owner"),
            updated_at=updated_at,
            source_system=common_source,
        )
    if entity_type == "deal":
        return CRMDeal(
            external_id=row.get("external_id"),
            company_external_id=row.get("linked_company_external_id"),
            name=row.get("name_or_title"),
            stage=row.get("stage_or_type"),
            owner=row.get("owner"),
            amount=_float_or_none(row.get("amount_or_valuation")),
            updated_at=updated_at,
            source_system=common_source,
        )
    if entity_type == "metric":
        return CRMMetric(
            external_id=row.get("external_id"),
            company_external_id=row.get("linked_company_external_id"),
            reporting_period=row.get("reporting_period"),
            revenue=_float_or_raw(row.get("revenue")),
            ebitda_margin=_float_or_raw(row.get("ebitda_margin")),
            burn_multiple=_float_or_raw(row.get("burn_multiple")),
            updated_at=updated_at,
            source_system=common_source,
        )
    if entity_type == "update":
        return CRMUpdate(
            external_id=row.get("external_id"),
            company_external_id=row.get("linked_company_external_id"),
            reporting_period=row.get("reporting_period"),
            update_type=row.get("stage_or_type"),
            summary=row.get("summary"),
            updated_at=updated_at,
            source_system=common_source,
        )
    return None
