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
