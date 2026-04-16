from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from db.models import CovenantBreach, DealPipeline, GeneratedReport, ReconciliationBreak, RejectedRecord, ReportingCompany, ReportingMetric, SyncRun

# PDF output is optional — weasyprint has heavy C dependencies.
try:
    from weasyprint import HTML as WeasyHTML  # type: ignore[import-untyped]
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


settings = get_settings()


INVESTOR_TEMPLATE = Template(
    """# Investor Update

- Sync run: {{ sync_run.id }}
- Status: {{ sync_run.status }}
- Generated at: {{ generated_at }}
- Companies in reporting layer: {{ companies|length }}
- Deal pipeline records: {{ deals|length }}

## New Companies and Deals
{% for company in companies[:5] %}
- {{ company.company_name }} | stage={{ company.stage }} | valuation={{ company.valuation or "n/a" }}
{% endfor %}
{% for deal in deals[:5] %}
- Deal: {{ deal.deal_name }} | stage={{ deal.stage }} | owner={{ deal.owner }}
{% endfor %}

## KPI Movement
{% for line in kpi_lines %}
- {{ line }}
{% endfor %}

## Records Needing Review
{% if rejected %}
{% for item in rejected %}
- {{ item.entity_type }} {{ item.source_external_id or "unknown" }}: {{ item.reason }}
{% endfor %}
{% else %}
- No rejected records in this run.
{% endif %}

## Sync Health
- Extracted: {{ sync_run.extracted_count }}
- Transformed: {{ sync_run.transformed_count }}
- Inserted: {{ sync_run.loaded_inserted_count }}
- Updated: {{ sync_run.loaded_updated_count }}
- Rejected: {{ sync_run.rejected_count }}
"""
)

INTERNAL_TEMPLATE = Template(
    """# Internal Ops Update

## Run Summary
- Sync run: {{ sync_run.id }}
- Trigger: {{ sync_run.trigger_mode }}
- Duration ms: {{ sync_run.duration_ms }}
- Checkpoint start: {{ sync_run.checkpoint_started_from }}
- Checkpoint end: {{ sync_run.checkpoint_ended_at }}

## Stage Changes and Exceptions
{% for deal in deals %}
- {{ deal.deal_name }} moved or remains at {{ deal.stage }} with owner {{ deal.owner }}
{% endfor %}

## KPI Exceptions
{% for line in kpi_lines %}
- {{ line }}
{% endfor %}

## Validation and Quarantine
{% if rejected %}
{% for item in rejected %}
- {{ item.entity_type }} rejected because {{ item.reason }}
{% endfor %}
{% else %}
- No quarantined records.
{% endif %}

## Warning Signals
{% if sync_run.warnings %}
{% for warning in sync_run.warnings %}
- {{ warning.entity }}: {{ warning.message }}
{% endfor %}
{% else %}
- No batch warnings.
{% endif %}
"""
)


HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ title }}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0; padding: 0;
      color: #1a2332;
      background: #f6f8fa;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    .report-shell { max-width: 780px; margin: 0 auto; padding: 40px 24px 60px; }
    .report-header {
      background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
      color: white;
      padding: 32px 28px;
      border-radius: 14px;
      margin-bottom: 28px;
    }
    .report-header h1 { margin: 0 0 8px; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
    .report-header .meta { opacity: 0.8; font-size: 13px; }
    .report-header .badge {
      display: inline-block;
      background: rgba(255,255,255,0.2);
      padding: 3px 10px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 600;
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .section {
      background: white;
      border: 1px solid #e1e5ea;
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .section h2 {
      font-size: 15px;
      font-weight: 650;
      color: #1a2332;
      margin: 0 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid #eef1f4;
    }
    ul { padding-left: 18px; margin: 0; }
    li { padding: 4px 0; font-size: 14px; color: #374151; }
    .metric-row {
      display: flex; justify-content: space-between; align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 14px;
    }
    .metric-row:last-child { border-bottom: none; }
    .metric-label { color: #6b7280; font-weight: 500; }
    .metric-value { font-weight: 700; font-family: "SF Mono", monospace; font-size: 13px; }
    .flag { color: #dc2626; font-weight: 600; }
    .success { color: #059669; }
    .footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; }
  </style>
</head>
<body>
  <div class="report-shell">
    <div class="report-header">
      <div class="badge">{{ title }}</div>
      <h1>Portfolio Report — Sync Run #{{ sync_run.id }}</h1>
      <div class="meta">Generated {{ generated_at }} &middot; Status: {{ sync_run.status }}</div>
    </div>
    <div class="section">
      <pre style="white-space:pre-wrap; font-family:inherit; font-size:14px; margin:0; color:#374151;">{{ markdown }}</pre>
    </div>
    <div class="footer">CRM-to-Reporting Automation &middot; Auto-generated report</div>
  </div>
</body>
</html>
"""
)


@dataclass
class ReportArtifacts:
    markdown_path: Path
    html_path: Path


def _build_kpi_lines(session: Session) -> list[str]:
    metrics = session.scalars(select(ReportingMetric).order_by(ReportingMetric.company_external_id)).all()
    lines: list[str] = []
    latest_by_company: dict[str, ReportingMetric] = {}
    prior_by_company: dict[str, ReportingMetric] = {}
    for metric in metrics:
        current = latest_by_company.get(metric.company_external_id)
        if current is None or metric.reporting_period > current.reporting_period:
            if current is not None:
                prior_by_company[metric.company_external_id] = current
            latest_by_company[metric.company_external_id] = metric
        elif metric.company_external_id not in prior_by_company or metric.reporting_period > prior_by_company[metric.company_external_id].reporting_period:
            prior_by_company[metric.company_external_id] = metric

    for company_id, latest in latest_by_company.items():
        prior = prior_by_company.get(company_id)
        if prior and latest.revenue is not None and prior.revenue is not None:
            delta = latest.revenue - prior.revenue
            lines.append(f"{company_id}: revenue moved by {delta:+,.0f} from {prior.reporting_period} to {latest.reporting_period}")
        elif latest.revenue is not None:
            lines.append(f"{company_id}: baseline revenue available for {latest.reporting_period} at {latest.revenue:,.0f}")
        else:
            lines.append(f"{company_id}: revenue missing in latest reporting period {latest.reporting_period}")
    return lines[:10]


def generate_reports(session: Session, sync_run: SyncRun) -> list[GeneratedReport]:
    companies = session.scalars(select(ReportingCompany).order_by(ReportingCompany.company_name)).all()
    deals = session.scalars(select(DealPipeline).order_by(DealPipeline.updated_at.desc())).all()
    rejected = session.scalars(select(RejectedRecord).where(RejectedRecord.sync_run_id == sync_run.id)).all()
    kpi_lines = _build_kpi_lines(session)

    generated_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    report_payloads = [
        ("investor", INVESTOR_TEMPLATE.render(sync_run=sync_run, companies=companies, deals=deals, rejected=rejected, kpi_lines=kpi_lines, generated_at=generated_at)),
        ("internal", INTERNAL_TEMPLATE.render(sync_run=sync_run, deals=deals[:10], rejected=rejected, kpi_lines=kpi_lines, generated_at=generated_at)),
    ]

    # Reconciliation + covenant data for enriched reports
    recon_breaks = session.scalars(select(ReconciliationBreak).where(ReconciliationBreak.sync_run_id == sync_run.id)).all()
    covenant_breaches = session.scalars(select(CovenantBreach).where(CovenantBreach.sync_run_id == sync_run.id)).all()

    created_reports: list[GeneratedReport] = []
    for report_type, markdown_body in report_payloads:
        # Append reconciliation + covenant sections to markdown
        if recon_breaks:
            markdown_body += "\n## Reconciliation Breaks (CRM vs Fund Admin)\n"
            for brk in recon_breaks:
                markdown_body += f"- {brk.borrower_name or brk.borrower_external_id}: {brk.field} — CRM={brk.crm_value} vs Admin={brk.fund_admin_value} [{brk.severity}]\n"
        if covenant_breaches:
            markdown_body += "\n## Covenant Breaches\n"
            for cb in covenant_breaches:
                markdown_body += f"- {cb.borrower_external_id} ({cb.covenant_type}): observed={cb.observed_value}, threshold {cb.comparison} {cb.threshold} [{cb.severity}]\n"

        base_name = f"sync_run_{sync_run.id}_{report_type}_update"
        markdown_path = settings.report_output_dir / f"{base_name}.md"
        html_path = settings.report_output_dir / f"{base_name}.html"
        markdown_path.write_text(markdown_body, encoding="utf-8")
        html_content = HTML_TEMPLATE.render(
            title=f"{report_type.title()} Update", markdown=markdown_body,
            generated_at=generated_at, sync_run=sync_run,
        )
        html_path.write_text(html_content, encoding="utf-8")
        created_reports.append(
            GeneratedReport(sync_run_id=sync_run.id, report_type=report_type, output_format="markdown", file_path=str(markdown_path))
        )
        created_reports.append(
            GeneratedReport(sync_run_id=sync_run.id, report_type=report_type, output_format="html", file_path=str(html_path))
        )

        # PDF output — optional, depends on weasyprint being installed
        if _PDF_AVAILABLE:
            try:
                pdf_path = settings.report_output_dir / f"{base_name}.pdf"
                WeasyHTML(string=html_content).write_pdf(str(pdf_path))
                created_reports.append(
                    GeneratedReport(sync_run_id=sync_run.id, report_type=report_type, output_format="pdf", file_path=str(pdf_path))
                )
            except Exception:
                import logging
                logging.getLogger(__name__).warning("PDF generation failed — skipping", exc_info=True)

    return created_reports
