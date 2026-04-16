from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from db.models import (
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


def seed_mock_crm(db: Session) -> None:
    for model in (
        CovenantBreach, ReconciliationBreak, GeneratedReport, RejectedRecord,
        SyncRun, ReportingUpdate, ReportingMetric, DealPipeline, ReportingCompany,
        FacilityCovenant, FundAdminRecord,
        CRMCompany, CRMContact, CRMDeal, CRMMetric, CRMUpdate,
    ):
        db.execute(delete(model))

    companies = [
        CRMCompany(external_id="COMP-100", name="Northstar Health", owner="Ava Chen", stage="portfolio", reporting_period="2026-Q1", valuation=125000000, updated_at=datetime.fromisoformat("2026-04-01T10:00:00"), source_system="mock_crm"),
        CRMCompany(external_id="COMP-101", name="Lattice Grid", owner="Daniel Ortiz", stage="qualified", reporting_period="2026-Q1", valuation=42000000, updated_at=datetime.fromisoformat("2026-04-03T09:30:00"), source_system="mock_crm"),
        # Intentional duplicate — same external_id, older timestamp (tests dedupe)
        CRMCompany(external_id="COMP-101", name="Lattice Grid", owner="Daniel Ortiz", stage="qualified", reporting_period="2026-Q1", valuation=42000000, updated_at=datetime.fromisoformat("2026-04-03T08:30:00"), source_system="mock_crm"),
        # Missing name — should be rejected by validation
        CRMCompany(external_id="COMP-102", name=None, owner="Sam Rivera", stage="new", reporting_period="2026-Q1", valuation=15000000, updated_at=datetime.fromisoformat("2026-04-02T11:00:00"), source_system="mock_crm"),
        # Missing owner — should be rejected
        CRMCompany(external_id="COMP-103", name="Beacon Logistics", owner=None, stage="monitoring", reporting_period="2026-Q1", valuation=87000000, updated_at=datetime.fromisoformat("2026-04-05T15:00:00"), source_system="mock_crm"),
        CRMCompany(external_id="COMP-104", name="Harbor Bio", owner="Ivy Shah", stage="portfolio", reporting_period="2025-Q4", valuation=99000000, updated_at=datetime.fromisoformat("2026-01-15T13:45:00"), source_system="mock_crm"),
        CRMCompany(external_id="COMP-105", name="Crestline AI", owner="Marcus Webb", stage="new", reporting_period="2026-Q1", valuation=28000000, updated_at=datetime.fromisoformat("2026-04-06T08:15:00"), source_system="mock_crm"),
        CRMCompany(external_id="COMP-106", name="Verdant Energy", owner="Ava Chen", stage="portfolio", reporting_period="2026-Q1", valuation=210000000, updated_at=datetime.fromisoformat("2026-04-07T14:00:00"), source_system="mock_crm"),
        CRMCompany(external_id="COMP-107", name="Pinnacle Fintech", owner="Daniel Ortiz", stage="monitoring", reporting_period="2026-Q1", valuation=64000000, updated_at=datetime.fromisoformat("2026-04-04T10:30:00"), source_system="mock_crm"),
        # Missing reporting_period — should be rejected
        CRMCompany(external_id="COMP-108", name="Stale Corp", owner="Ops Queue", stage="realized", reporting_period=None, valuation=5000000, updated_at=datetime.fromisoformat("2025-11-01T09:00:00"), source_system="mock_crm"),
    ]

    contacts = [
        CRMContact(external_id="CONT-200", company_external_id="COMP-100", full_name="Mina Foster", email="mina@northstar.test", owner="Ava Chen", updated_at=datetime.fromisoformat("2026-04-01T12:00:00"), source_system="mock_crm"),
        CRMContact(external_id="CONT-201", company_external_id="COMP-101", full_name="Leo Park", email="leo@lattice.test", owner="Daniel Ortiz", updated_at=datetime.fromisoformat("2026-04-03T12:30:00"), source_system="mock_crm"),
        CRMContact(external_id="CONT-202", company_external_id="COMP-104", full_name="Priya Nair", email="priya@harborbio.test", owner="Ivy Shah", updated_at=datetime.fromisoformat("2026-03-20T09:00:00"), source_system="mock_crm"),
        CRMContact(external_id="CONT-203", company_external_id="COMP-105", full_name="Jordan Blake", email="jordan@crestline.test", owner="Marcus Webb", updated_at=datetime.fromisoformat("2026-04-06T10:00:00"), source_system="mock_crm"),
        CRMContact(external_id="CONT-204", company_external_id="COMP-106", full_name="Nadia Reeves", email="nadia@verdant.test", owner="Ava Chen", updated_at=datetime.fromisoformat("2026-04-07T15:00:00"), source_system="mock_crm"),
    ]

    deals = [
        CRMDeal(external_id="DEAL-300", company_external_id="COMP-101", name="Lattice Series B", stage="ic", owner="Daniel Ortiz", amount=18000000, updated_at=datetime.fromisoformat("2026-04-03T14:00:00"), source_system="mock_crm"),
        CRMDeal(external_id="DEAL-301", company_external_id="COMP-104", name="Harbor Follow-on", stage="term_sheet", owner="Ivy Shah", amount=12000000, updated_at=datetime.fromisoformat("2026-04-05T18:00:00"), source_system="mock_crm"),
        # Invalid stage — should be rejected
        CRMDeal(external_id="DEAL-302", company_external_id="COMP-999", name="Broken Deal", stage="mystery_stage", owner="Ops Queue", amount=2500000, updated_at=datetime.fromisoformat("2026-04-02T18:00:00"), source_system="mock_crm"),
        CRMDeal(external_id="DEAL-303", company_external_id="COMP-105", name="Crestline Seed Extension", stage="screening", owner="Marcus Webb", amount=5000000, updated_at=datetime.fromisoformat("2026-04-06T11:00:00"), source_system="mock_crm"),
        CRMDeal(external_id="DEAL-304", company_external_id="COMP-106", name="Verdant Growth Round", stage="closed_won", owner="Ava Chen", amount=45000000, updated_at=datetime.fromisoformat("2026-04-07T16:00:00"), source_system="mock_crm"),
        CRMDeal(external_id="DEAL-305", company_external_id="COMP-107", name="Pinnacle Bridge Note", stage="sourced", owner="Daniel Ortiz", amount=8000000, updated_at=datetime.fromisoformat("2026-04-04T12:00:00"), source_system="mock_crm"),
    ]

    metrics = [
        CRMMetric(external_id="MET-400", company_external_id="COMP-100", reporting_period="2025-Q4", revenue=14000000, ebitda_margin=0.12, burn_multiple=1.4, updated_at=datetime.fromisoformat("2026-01-15T10:00:00"), source_system="mock_crm"),
        CRMMetric(external_id="MET-401", company_external_id="COMP-100", reporting_period="2026-Q1", revenue=15600000, ebitda_margin=0.15, burn_multiple=1.2, updated_at=datetime.fromisoformat("2026-04-01T16:00:00"), source_system="mock_crm"),
        # Non-numeric revenue — should be rejected
        CRMMetric(external_id="MET-402", company_external_id="COMP-101", reporting_period="2026-Q1", revenue="not_a_number", ebitda_margin=0.08, burn_multiple=2.1, updated_at=datetime.fromisoformat("2026-04-03T17:00:00"), source_system="mock_crm"),  # type: ignore[arg-type]
        CRMMetric(external_id="MET-403", company_external_id="COMP-104", reporting_period="2025-Q4", revenue=9800000, ebitda_margin=0.21, burn_multiple=0.9, updated_at=datetime.fromisoformat("2026-01-16T09:00:00"), source_system="mock_crm"),
        # Intentional duplicate — same external_id, older timestamp (tests dedupe)
        CRMMetric(external_id="MET-403", company_external_id="COMP-104", reporting_period="2025-Q4", revenue=9800000, ebitda_margin=0.21, burn_multiple=0.9, updated_at=datetime.fromisoformat("2026-01-15T09:00:00"), source_system="mock_crm"),
        CRMMetric(external_id="MET-404", company_external_id="COMP-106", reporting_period="2025-Q4", revenue=31000000, ebitda_margin=0.18, burn_multiple=0.7, updated_at=datetime.fromisoformat("2026-01-20T11:00:00"), source_system="mock_crm"),
        CRMMetric(external_id="MET-405", company_external_id="COMP-106", reporting_period="2026-Q1", revenue=36500000, ebitda_margin=0.22, burn_multiple=0.6, updated_at=datetime.fromisoformat("2026-04-07T17:00:00"), source_system="mock_crm"),
        CRMMetric(external_id="MET-406", company_external_id="COMP-107", reporting_period="2026-Q1", revenue=7200000, ebitda_margin=-0.05, burn_multiple=3.2, updated_at=datetime.fromisoformat("2026-04-04T14:00:00"), source_system="mock_crm"),
    ]

    updates = [
        CRMUpdate(external_id="UPD-500", company_external_id="COMP-100", reporting_period="2026-Q1", update_type="investor", summary="Northstar signed two new provider networks and exceeded plan. ARR grew 11% QoQ to $15.6M, with gross margin expanding to 68%.", updated_at=datetime.fromisoformat("2026-04-01T19:00:00"), source_system="mock_crm"),
        CRMUpdate(external_id="UPD-501", company_external_id="COMP-101", reporting_period="2026-Q1", update_type="internal", summary="Lattice Grid advanced to IC with diligence still open on churn drivers. Series B pricing expected at $42M pre-money.", updated_at=datetime.fromisoformat("2026-04-03T19:30:00"), source_system="mock_crm"),
        # Empty summary — should be rejected
        CRMUpdate(external_id="UPD-502", company_external_id="COMP-103", reporting_period="2026-Q1", update_type="portfolio", summary="", updated_at=datetime.fromisoformat("2026-04-05T11:00:00"), source_system="mock_crm"),
        CRMUpdate(external_id="UPD-503", company_external_id="COMP-106", reporting_period="2026-Q1", update_type="investor", summary="Verdant closed $45M growth round led by our fund. Revenue grew 18% QoQ. Expansion into commercial solar on track for Q2 launch.", updated_at=datetime.fromisoformat("2026-04-07T18:00:00"), source_system="mock_crm"),
        CRMUpdate(external_id="UPD-504", company_external_id="COMP-104", reporting_period="2025-Q4", update_type="portfolio", summary="Harbor Bio completed Phase IIa milestones on schedule. Cash runway extended to Q3 2027 with follow-on capital.", updated_at=datetime.fromisoformat("2026-01-16T12:00:00"), source_system="mock_crm"),
    ]

    # ------------------------------------------------------------------
    # Fund admin records — what SS&C / Citco has on file.
    # Intentional discrepancies vs CRM to demonstrate reconciliation:
    #   COMP-100: valuation off by $3M (CRM $125M vs admin $122M)
    #   COMP-104: stage mismatch (CRM "portfolio" vs admin "monitoring")
    #   COMP-106: valuation off by $15M (CRM $210M vs admin $195M) — material
    #   COMP-107: principal balance exists only in admin (no CRM match field)
    # ------------------------------------------------------------------
    fund_admin_records = [
        FundAdminRecord(external_id="FA-100", borrower_external_id="COMP-100", borrower_name="Northstar Health", reporting_period="2026-Q1", fund_admin_valuation=122000000, fund_admin_principal_balance=50000000, fund_admin_stage="portfolio", as_of_date=datetime.fromisoformat("2026-04-01T00:00:00"), source_system="mock_fund_admin"),
        FundAdminRecord(external_id="FA-101", borrower_external_id="COMP-101", borrower_name="Lattice Grid", reporting_period="2026-Q1", fund_admin_valuation=42000000, fund_admin_principal_balance=None, fund_admin_stage="qualified", as_of_date=datetime.fromisoformat("2026-04-03T00:00:00"), source_system="mock_fund_admin"),
        FundAdminRecord(external_id="FA-104", borrower_external_id="COMP-104", borrower_name="Harbor Bio", reporting_period="2025-Q4", fund_admin_valuation=99000000, fund_admin_principal_balance=35000000, fund_admin_stage="monitoring", as_of_date=datetime.fromisoformat("2026-01-15T00:00:00"), source_system="mock_fund_admin"),
        FundAdminRecord(external_id="FA-106", borrower_external_id="COMP-106", borrower_name="Verdant Energy", reporting_period="2026-Q1", fund_admin_valuation=195000000, fund_admin_principal_balance=80000000, fund_admin_stage="portfolio", as_of_date=datetime.fromisoformat("2026-04-07T00:00:00"), source_system="mock_fund_admin"),
        FundAdminRecord(external_id="FA-107", borrower_external_id="COMP-107", borrower_name="Pinnacle Fintech", reporting_period="2026-Q1", fund_admin_valuation=64000000, fund_admin_principal_balance=25000000, fund_admin_stage="monitoring", as_of_date=datetime.fromisoformat("2026-04-04T00:00:00"), source_system="mock_fund_admin"),
    ]

    # ------------------------------------------------------------------
    # Facility covenants — thresholds a borrower must meet each quarter.
    # Seeded against closed/active deals.
    # ------------------------------------------------------------------
    covenants = [
        # Verdant Growth Round — closed_won, healthy
        FacilityCovenant(facility_external_id="DEAL-304", borrower_external_id="COMP-106", covenant_type="min_ebitda_margin", threshold=0.10, comparison=">=", description="EBITDA margin must stay above 10%"),
        FacilityCovenant(facility_external_id="DEAL-304", borrower_external_id="COMP-106", covenant_type="max_leverage", threshold=5.0, comparison="<=", description="Debt/EBITDA must not exceed 5.0x"),
        # Pinnacle Bridge Note — sourced, but covenant pre-set for IC
        FacilityCovenant(facility_external_id="DEAL-305", borrower_external_id="COMP-107", covenant_type="min_ebitda_margin", threshold=0.0, comparison=">=", description="EBITDA margin must be non-negative"),
        FacilityCovenant(facility_external_id="DEAL-305", borrower_external_id="COMP-107", covenant_type="max_burn_multiple", threshold=2.5, comparison="<=", description="Burn multiple must not exceed 2.5x"),
        # Harbor Follow-on — term_sheet
        FacilityCovenant(facility_external_id="DEAL-301", borrower_external_id="COMP-104", covenant_type="min_ebitda_margin", threshold=0.15, comparison=">=", description="EBITDA margin >= 15%"),
        # Northstar (no deal in pipeline but has metrics) — attach to a synthetic facility for demo
        FacilityCovenant(facility_external_id="DEAL-SYNTH-100", borrower_external_id="COMP-100", covenant_type="max_burn_multiple", threshold=2.0, comparison="<=", description="Burn multiple must not exceed 2.0x"),
    ]

    db.add_all(companies + contacts + deals + metrics + updates + fund_admin_records + covenants)
    db.commit()
