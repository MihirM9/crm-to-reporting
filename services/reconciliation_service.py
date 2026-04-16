"""Reconciliation service — diffs CRM reporting layer vs fund admin positions.

In a real private credit fund, this runs quarterly after fund admin delivers
their CSV/SFTP extract. The output is a set of 'breaks' — fields where the
two sources disagree — that a back-office analyst reviews before sign-off.

Breaks are persisted to `reconciliation_breaks` for audit trail.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import FundAdminRecord, ReconciliationBreak, ReportingCompany


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _severity_for_pct(pct: float | None) -> str:
    """Classify break severity based on magnitude."""
    if pct is None:
        return "info"
    abs_pct = abs(pct)
    if abs_pct >= 10.0:
        return "critical"
    if abs_pct >= 2.0:
        return "warning"
    return "info"


def run_reconciliation(db: Session, sync_run_id: int) -> list[ReconciliationBreak]:
    """Compare CRM reporting companies against fund admin positions.

    Returns a list of ReconciliationBreak objects (already added to session,
    not yet committed — the caller is expected to commit).
    """
    admin_records = db.scalars(select(FundAdminRecord)).all()
    admin_by_borrower: dict[str, FundAdminRecord] = {
        r.borrower_external_id: r for r in admin_records
    }

    crm_companies = db.scalars(select(ReportingCompany)).all()
    crm_by_id: dict[str, ReportingCompany] = {
        c.external_id: c for c in crm_companies
    }

    breaks: list[ReconciliationBreak] = []

    for borrower_id, admin in admin_by_borrower.items():
        crm = crm_by_id.get(borrower_id)
        if crm is None:
            # Fund admin has a position the reporting layer doesn't — notable
            breaks.append(ReconciliationBreak(
                sync_run_id=sync_run_id,
                borrower_external_id=borrower_id,
                borrower_name=admin.borrower_name,
                field="presence",
                crm_value=None,
                fund_admin_value="exists",
                break_magnitude=None,
                break_pct=None,
                severity="warning",
                detected_at=utcnow(),
            ))
            continue

        # --- Valuation comparison ---
        if admin.fund_admin_valuation is not None and crm.valuation is not None:
            delta = crm.valuation - admin.fund_admin_valuation
            pct = (delta / admin.fund_admin_valuation * 100) if admin.fund_admin_valuation else None
            if abs(delta) > 0:
                breaks.append(ReconciliationBreak(
                    sync_run_id=sync_run_id,
                    borrower_external_id=borrower_id,
                    borrower_name=crm.company_name,
                    field="valuation",
                    crm_value=str(crm.valuation),
                    fund_admin_value=str(admin.fund_admin_valuation),
                    break_magnitude=abs(delta),
                    break_pct=round(pct, 2) if pct is not None else None,
                    severity=_severity_for_pct(pct),
                    detected_at=utcnow(),
                ))

        # --- Stage comparison ---
        if admin.fund_admin_stage and crm.stage and admin.fund_admin_stage != crm.stage:
            breaks.append(ReconciliationBreak(
                sync_run_id=sync_run_id,
                borrower_external_id=borrower_id,
                borrower_name=crm.company_name,
                field="stage",
                crm_value=crm.stage,
                fund_admin_value=admin.fund_admin_stage,
                break_magnitude=None,
                break_pct=None,
                severity="warning",
                detected_at=utcnow(),
            ))

    for brk in breaks:
        db.add(brk)

    if breaks:
        logger.info(
            "Reconciliation completed",
            extra={
                "event": "reconciliation_completed",
                "context": {"sync_run_id": sync_run_id, "breaks_found": len(breaks)},
            },
        )
    return breaks
