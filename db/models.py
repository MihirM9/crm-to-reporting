from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class CRMCompany(Base, TimestampMixin):
    __tablename__ = "crm_companies"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    name = Column(String(255), nullable=True)
    owner = Column(String(128), nullable=True)
    stage = Column(String(64), nullable=True)
    reporting_period = Column(String(32), nullable=True)
    valuation = Column(Float, nullable=True)
    source_system = Column(String(64), default="mock_crm")
    status = Column(String(32), default="active")


class CRMContact(Base, TimestampMixin):
    __tablename__ = "crm_contacts"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    company_external_id = Column(String(64), nullable=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    owner = Column(String(128), nullable=True)
    source_system = Column(String(64), default="mock_crm")


class CRMDeal(Base, TimestampMixin):
    __tablename__ = "crm_deals"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    company_external_id = Column(String(64), nullable=True)
    name = Column(String(255), nullable=True)
    stage = Column(String(64), nullable=True)
    owner = Column(String(128), nullable=True)
    amount = Column(Float, nullable=True)
    source_system = Column(String(64), default="mock_crm")


class CRMMetric(Base, TimestampMixin):
    __tablename__ = "crm_metrics"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    company_external_id = Column(String(64), nullable=True)
    reporting_period = Column(String(32), nullable=True)
    revenue = Column(JSON, nullable=True)
    ebitda_margin = Column(JSON, nullable=True)
    burn_multiple = Column(JSON, nullable=True)
    source_system = Column(String(64), default="mock_crm")


class CRMUpdate(Base, TimestampMixin):
    __tablename__ = "crm_updates"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    company_external_id = Column(String(64), nullable=True)
    reporting_period = Column(String(32), nullable=True)
    update_type = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    source_system = Column(String(64), default="mock_crm")


class ReportingCompany(Base, TimestampMixin):
    __tablename__ = "reporting_companies"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True)
    company_name = Column(String(255), nullable=False)
    owner = Column(String(128), nullable=False)
    stage = Column(String(64), nullable=False)
    reporting_period = Column(String(32), nullable=False)
    valuation = Column(Float, nullable=True)
    source_system = Column(String(64), nullable=False)
    crm_updated_at = Column(DateTime, nullable=False)
    last_sync_run_id = Column(Integer, nullable=True)


class ReportingUpdate(Base, TimestampMixin):
    __tablename__ = "reporting_updates"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True)
    company_external_id = Column(String(64), index=True, nullable=False)
    reporting_period = Column(String(32), nullable=False)
    update_type = Column(String(32), nullable=False)
    summary = Column(Text, nullable=False)
    source_system = Column(String(64), nullable=False)
    crm_updated_at = Column(DateTime, nullable=False)
    last_sync_run_id = Column(Integer, nullable=True)


class ReportingMetric(Base, TimestampMixin):
    __tablename__ = "reporting_metrics"

    id = Column(Integer, primary_key=True)
    dedupe_key = Column(String(128), unique=True, index=True)
    external_id = Column(String(64), nullable=True)
    company_external_id = Column(String(64), index=True, nullable=False)
    reporting_period = Column(String(32), nullable=False)
    revenue = Column(Float, nullable=True)
    ebitda_margin = Column(Float, nullable=True)
    burn_multiple = Column(Float, nullable=True)
    source_system = Column(String(64), nullable=False)
    crm_updated_at = Column(DateTime, nullable=False)
    last_sync_run_id = Column(Integer, nullable=True)


class DealPipeline(Base, TimestampMixin):
    __tablename__ = "deal_pipeline"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True)
    company_external_id = Column(String(64), nullable=True)
    deal_name = Column(String(255), nullable=False)
    stage = Column(String(64), nullable=False)
    owner = Column(String(128), nullable=False)
    amount = Column(Float, nullable=True)
    source_system = Column(String(64), nullable=False)
    crm_updated_at = Column(DateTime, nullable=False)
    last_sync_run_id = Column(Integer, nullable=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True)
    trigger_mode = Column(String(32), nullable=False)
    status = Column(String(32), default="running")
    started_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    extracted_count = Column(Integer, default=0)
    transformed_count = Column(Integer, default=0)
    loaded_inserted_count = Column(Integer, default=0)
    loaded_updated_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    status_message = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=True)
    checkpoint_started_from = Column(DateTime, nullable=True)
    checkpoint_ended_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)


class RejectedRecord(Base):
    __tablename__ = "rejected_records"

    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, index=True, nullable=False)
    entity_type = Column(String(64), nullable=False)
    source_external_id = Column(String(64), nullable=True)
    reason = Column(Text, nullable=False)
    details = Column(JSON, nullable=False)
    raw_record = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, index=True, nullable=False)
    report_type = Column(String(32), nullable=False)
    output_format = Column(String(16), nullable=False)
    file_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class AppState(Base):
    __tablename__ = "app_state"

    key = Column(String(64), primary_key=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Fund admin source + reconciliation
# ---------------------------------------------------------------------------

class FundAdminRecord(Base, TimestampMixin):
    """Mock fund admin (SS&C/Citco/Alter Domus) position record.

    In reality this would come from a quarterly CSV/SFTP drop or an API.
    We keep it local so the reconciliation service can diff against CRM.
    """
    __tablename__ = "fund_admin_records"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), index=True)
    borrower_external_id = Column(String(64), index=True, nullable=False)
    borrower_name = Column(String(255), nullable=False)
    reporting_period = Column(String(32), nullable=False)
    # What fund admin has on file
    fund_admin_valuation = Column(Float, nullable=True)
    fund_admin_principal_balance = Column(Float, nullable=True)
    fund_admin_stage = Column(String(64), nullable=True)
    as_of_date = Column(DateTime, nullable=False)
    source_system = Column(String(64), default="mock_fund_admin")


class ReconciliationBreak(Base):
    """A diff between CRM and fund admin for the same borrower.

    Auditable record: every detected break is written here with both values
    and the magnitude, so a back-office analyst (or an auditor) can reproduce it.
    """
    __tablename__ = "reconciliation_breaks"

    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, index=True, nullable=False)
    borrower_external_id = Column(String(64), index=True, nullable=False)
    borrower_name = Column(String(255), nullable=True)
    field = Column(String(64), nullable=False)   # e.g. "valuation", "stage"
    crm_value = Column(String(255), nullable=True)
    fund_admin_value = Column(String(255), nullable=True)
    break_magnitude = Column(Float, nullable=True)   # absolute delta for numeric fields
    break_pct = Column(Float, nullable=True)
    severity = Column(String(16), nullable=False)   # info / warning / critical
    detected_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Covenant compliance
# ---------------------------------------------------------------------------

class FacilityCovenant(Base, TimestampMixin):
    """A numeric covenant attached to a credit facility.

    Examples:
      - DSCR (Debt Service Coverage Ratio) >= 1.25
      - LTV (Loan-to-Value) <= 0.65
      - Max Leverage (Debt/EBITDA) <= 5.0
      - Min EBITDA margin >= 0.10
    """
    __tablename__ = "facility_covenants"

    id = Column(Integer, primary_key=True)
    facility_external_id = Column(String(64), index=True, nullable=False)
    borrower_external_id = Column(String(64), index=True, nullable=False)
    covenant_type = Column(String(32), nullable=False)   # dscr / ltv / max_leverage / min_ebitda_margin
    threshold = Column(Float, nullable=False)
    comparison = Column(String(8), nullable=False)    # "<=", ">=", "<", ">"
    description = Column(String(255), nullable=True)


class CovenantBreach(Base):
    """A detected covenant breach recorded during a sync run."""
    __tablename__ = "covenant_breaches"

    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, index=True, nullable=False)
    covenant_id = Column(Integer, index=True, nullable=False)
    facility_external_id = Column(String(64), nullable=False)
    borrower_external_id = Column(String(64), nullable=False)
    covenant_type = Column(String(32), nullable=False)
    threshold = Column(Float, nullable=False)
    comparison = Column(String(8), nullable=False)
    observed_value = Column(Float, nullable=True)
    reporting_period = Column(String(32), nullable=True)
    severity = Column(String(16), nullable=False)   # warning / critical
    detected_at = Column(DateTime, default=utcnow)
