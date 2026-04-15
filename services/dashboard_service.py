from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    CRMCompany,
    CRMContact,
    CRMDeal,
    CRMMetric,
    CRMUpdate,
    DealPipeline,
    GeneratedReport,
    RejectedRecord,
    ReportingCompany,
    ReportingMetric,
    ReportingUpdate,
    SyncRun,
)


def get_dashboard_context(db: Session) -> dict:
    latest_run = db.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()))
    recent_runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(20)).all()
    rejected = db.scalars(select(RejectedRecord).order_by(RejectedRecord.created_at.desc()).limit(25)).all()
    reports = db.scalars(select(GeneratedReport).order_by(GeneratedReport.created_at.desc()).limit(20)).all()

    # CRM source counts
    crm_company_count = db.scalar(select(func.count()).select_from(CRMCompany)) or 0
    crm_contact_count = db.scalar(select(func.count()).select_from(CRMContact)) or 0
    crm_deal_count = db.scalar(select(func.count()).select_from(CRMDeal)) or 0
    crm_metric_count = db.scalar(select(func.count()).select_from(CRMMetric)) or 0
    crm_update_count = db.scalar(select(func.count()).select_from(CRMUpdate)) or 0

    # Reporting layer counts
    rpt_company_count = db.scalar(select(func.count()).select_from(ReportingCompany)) or 0
    rpt_deal_count = db.scalar(select(func.count()).select_from(DealPipeline)) or 0
    rpt_metric_count = db.scalar(select(func.count()).select_from(ReportingMetric)) or 0
    rpt_update_count = db.scalar(select(func.count()).select_from(ReportingUpdate)) or 0

    # CRM records for browsing
    crm_companies = db.scalars(select(CRMCompany).order_by(CRMCompany.updated_at.desc())).all()
    crm_contacts = db.scalars(select(CRMContact).order_by(CRMContact.updated_at.desc())).all()
    crm_deals = db.scalars(select(CRMDeal).order_by(CRMDeal.updated_at.desc())).all()

    # Reporting records for browsing
    rpt_companies = db.scalars(select(ReportingCompany).order_by(ReportingCompany.company_name)).all()
    rpt_deals = db.scalars(select(DealPipeline).order_by(DealPipeline.updated_at.desc())).all()
    rpt_metrics = db.scalars(select(ReportingMetric).order_by(ReportingMetric.company_external_id)).all()

    # Sync stats
    total_syncs = db.scalar(select(func.count()).select_from(SyncRun)) or 0
    successful_syncs = db.scalar(select(func.count()).select_from(SyncRun).where(SyncRun.status == "success")) or 0
    failed_syncs = db.scalar(select(func.count()).select_from(SyncRun).where(SyncRun.status == "failed")) or 0
    total_rejected = db.scalar(select(func.count()).select_from(RejectedRecord)) or 0

    return {
        "latest_run": latest_run,
        "recent_runs": recent_runs,
        "rejected": rejected,
        "reports": reports,
        # CRM counts
        "crm_company_count": crm_company_count,
        "crm_contact_count": crm_contact_count,
        "crm_deal_count": crm_deal_count,
        "crm_metric_count": crm_metric_count,
        "crm_update_count": crm_update_count,
        # Reporting counts
        "rpt_company_count": rpt_company_count,
        "rpt_deal_count": rpt_deal_count,
        "rpt_metric_count": rpt_metric_count,
        "rpt_update_count": rpt_update_count,
        # CRM records
        "crm_companies": crm_companies,
        "crm_contacts": crm_contacts,
        "crm_deals": crm_deals,
        # Reporting records
        "rpt_companies": rpt_companies,
        "rpt_deals": rpt_deals,
        "rpt_metrics": rpt_metrics,
        # Stats
        "total_syncs": total_syncs,
        "successful_syncs": successful_syncs,
        "failed_syncs": failed_syncs,
        "total_rejected": total_rejected,
    }
