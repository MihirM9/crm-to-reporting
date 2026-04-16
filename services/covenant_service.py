"""Covenant compliance service — checks borrower metrics against facility covenants.

After each sync, we read the latest metrics for each borrower and test them
against the covenants attached to their facilities. Breaches are persisted
to `covenant_breaches` for audit trail and surfaced via the MCP watchlist.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CovenantBreach, FacilityCovenant, ReportingMetric


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Map covenant_type → which metric field to check
_METRIC_FIELD_MAP: dict[str, str] = {
    "min_ebitda_margin": "ebitda_margin",
    "max_leverage": "burn_multiple",       # proxy — real leverage would be Debt/EBITDA
    "max_burn_multiple": "burn_multiple",
    "min_revenue": "revenue",
}


def _test_covenant(covenant: FacilityCovenant, observed: float | None) -> bool:
    """Return True if the covenant is BREACHED."""
    if observed is None:
        return False  # can't test without data — not a breach, but may flag elsewhere
    comp = covenant.comparison
    t = covenant.threshold
    if comp == ">=":
        return observed < t
    if comp == ">":
        return observed <= t
    if comp == "<=":
        return observed > t
    if comp == "<":
        return observed >= t
    return False


def check_covenants(db: Session, sync_run_id: int) -> list[CovenantBreach]:
    """Evaluate all facility covenants against latest borrower metrics.

    Returns a list of CovenantBreach objects (already added to session,
    not yet committed).
    """
    covenants = db.scalars(select(FacilityCovenant)).all()
    if not covenants:
        return []

    # Build latest-metric lookup by borrower
    all_metrics = db.scalars(
        select(ReportingMetric).order_by(
            ReportingMetric.company_external_id, ReportingMetric.reporting_period
        )
    ).all()
    latest_metric: dict[str, ReportingMetric] = {}
    for m in all_metrics:
        cur = latest_metric.get(m.company_external_id)
        if cur is None or m.reporting_period > cur.reporting_period:
            latest_metric[m.company_external_id] = m

    breaches: list[CovenantBreach] = []
    for cov in covenants:
        metric = latest_metric.get(cov.borrower_external_id)
        if metric is None:
            continue

        field_name = _METRIC_FIELD_MAP.get(cov.covenant_type)
        if field_name is None:
            continue

        observed = getattr(metric, field_name, None)
        if _test_covenant(cov, observed):
            severity = "critical" if cov.covenant_type.startswith("min_ebitda") else "warning"
            breach = CovenantBreach(
                sync_run_id=sync_run_id,
                covenant_id=cov.id,
                facility_external_id=cov.facility_external_id,
                borrower_external_id=cov.borrower_external_id,
                covenant_type=cov.covenant_type,
                threshold=cov.threshold,
                comparison=cov.comparison,
                observed_value=observed,
                reporting_period=metric.reporting_period,
                severity=severity,
                detected_at=utcnow(),
            )
            db.add(breach)
            breaches.append(breach)

    if breaches:
        logger.info(
            "Covenant check completed",
            extra={
                "event": "covenant_check_completed",
                "context": {"sync_run_id": sync_run_id, "breaches_found": len(breaches)},
            },
        )
    return breaches
