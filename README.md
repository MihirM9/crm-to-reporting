![CI](https://github.com/MihirM9/crm-to-reporting/actions/workflows/ci.yml/badge.svg)

# CRM-to-Reporting Pipeline Demo for Private Credit

Production-aware demo of a CRM-to-reporting pipeline with validation, two-source reconciliation, covenant monitoring, and an MCP agent interface for private credit ops.

This repository is a **demo**, not a production deployment. The orchestration, validation, reconciliation, reporting, and MCP patterns are meant to be realistic; the source systems and sample data in this repo are intentionally mocked so the workflow is easy to run locally and easy to review in an interview or design discussion.

## What this repo actually includes

- A Flask app with:
  - a mock CRM API
  - a mock fund admin API
  - a small internal-ops dashboard
  - REST endpoints to inspect data and trigger syncs
- A sync pipeline that:
  - fetches incremental updates over REST
  - retries transient failures
  - validates records
  - quarantines bad rows
  - deduplicates deterministically
  - upserts idempotently into a reporting layer
- Post-load checks for:
  - CRM vs fund admin reconciliation
  - covenant compliance monitoring
- Report generation for:
  - investor updates
  - internal ops updates
  - Markdown and HTML outputs
  - optional PDF output if `weasyprint` is installed
- An MCP server that exposes operational read/write tools against the same reporting layer

## Demo status and scope

What is real in this repo:

- The sync orchestration flow
- Validation and quarantine handling
- Idempotent loading patterns
- Reconciliation logic
- Covenant checks
- Report templates and file generation
- MCP tool wiring and tests
- GitHub CI

What is mock or simplified:

- CRM source data
- Fund admin source data
- Authentication and secrets handling
- Scheduler deployment model
- Storage choice and infra
- PDF generation dependency management
- Any claim of direct integration with a live vendor system

If you want to adapt this toward a live environment, start with the adapter examples in [examples/real_crm_adapter.py](/Users/mihir/Downloads/CRM%20to%20Reporting/examples/real_crm_adapter.py) and [examples/fund_admin_csv_loader.py](/Users/mihir/Downloads/CRM%20to%20Reporting/examples/fund_admin_csv_loader.py), then swap the source clients while keeping the reporting layer, validation, dedupe, reconciliation, and report generation flows intact.

## UI and output notes

The dashboard is intentionally small and operational. It exposes the same core surfaces an internal ops or portfolio-monitoring workflow would care about:

- latest sync status
- rejected and quarantined rows
- reconciliation breaks
- covenant breaches
- generated investor and internal updates

The current README stays text-first on purpose. If you want visual assets later, they should be captured from the running app rather than added as conceptual mockups.

## End-to-end flow

```text
Mock CRM API           Mock Fund Admin API
      |                        |
      +---- REST pull ---------+
               |
               v
        Sync / ETL service
        - incremental checkpoints
        - retries/backoff
        - validation
        - dedupe
        - idempotent upserts
        - quarantine
               |
               v
         Reporting layer
               |
      +--------+--------+
      |                 |
      v                 v
Reconciliation     Covenant checks
      |                 |
      +--------+--------+
               |
               v
         Reports + Dashboard + MCP tools
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/seed_demo.py
python scripts/run_sync_once.py
python main.py
```

Open:

- Dashboard: `http://127.0.0.1:8000`
- API reference page: `http://127.0.0.1:8000/api-docs`

## What to click first

1. Open the dashboard overview and inspect the latest run, sync totals, reconciliation count, and covenant breach count.
2. Open the rejected-records section to see quarantined rows with human-readable reasons.
3. Open the reporting layer section to confirm deduped, normalized records landed correctly.
4. Open the reports section to inspect the investor/internal outputs.
5. Use the MCP server or API endpoints to query the same data without using the UI.

## API surface in plain English

Source APIs:

- `GET /api/mock-crm/companies`
- `GET /api/mock-crm/contacts`
- `GET /api/mock-crm/deals`
- `GET /api/mock-crm/metrics`
- `GET /api/mock-crm/updates`
- `GET /api/mock-admin/positions`

Operational endpoints:

- `POST /api/jobs/run-sync`
- `GET /api/jobs/latest-sync`
- `GET /api/reporting/companies`
- `GET /api/reporting/deal-pipeline`
- `GET /api/reporting/metrics`
- `GET /api/reporting/updates`
- `GET /api/reporting/sync-runs`
- `GET /api/reporting/rejected-records`
- `GET /api/reporting/reconciliation-breaks`
- `GET /api/reporting/covenant-breaches`
- `GET /api/reporting/reports`

## Real-ish integration example

The repo currently runs against mock source systems. To make the boundary clearer, there are two minimal extension examples here:

- CRM REST adapter example: [examples/real_crm_adapter.py](/Users/mihir/Downloads/CRM%20to%20Reporting/examples/real_crm_adapter.py)
- Fund admin CSV loader example: [examples/fund_admin_csv_loader.py](/Users/mihir/Downloads/CRM%20to%20Reporting/examples/fund_admin_csv_loader.py)

That example shows how to:

- read credentials from environment variables
- call a real paginated CRM API with `updated_since`
- normalize vendor-shaped payloads into this repo’s internal record shape
- keep the downstream sync/reporting logic unchanged

This is the intended extension path: replace source adapters first, not the reporting layer or validation pipeline.

## MCP agent interface

The MCP layer is present because the reporting datastore is more useful if an operator or PM can query it directly from an agent client.

Example prompts:

- “Run the latest sync and summarize any rejected records.”
- “Show me reconciliation breaks for Harbor Bio.”
- “Which borrowers tripped covenant checks this quarter?”
- “Read the latest investor update.”

Typical tools exposed:

- `run_sync`
- `get_latest_sync`
- `list_sync_runs`
- `list_borrowers`
- `list_facilities`
- `get_kpi_movements`
- `list_watchlist`
- `list_rejected_records`
- `list_reconciliation_breaks`
- `list_covenant_breaches`
- `list_reports`
- `read_report`
- `get_pipeline_stats`

To wire it into Claude Code or another MCP client, use the local server module from [.mcp.json](/Users/mihir/Downloads/CRM%20to%20Reporting/.mcp.json) as the starting point.

## Validation, reconciliation, and reporting behaviors

Validation and quarantine:

- required fields are checked at row level
- malformed values are rejected with human-readable reasons
- bad records go to `rejected_records`
- one bad row does not stop the full sync run

Reconciliation:

- compares reporting-layer borrower records to fund admin positions
- writes valuation and stage breaks to `reconciliation_breaks`
- classifies break severity

Covenant monitoring:

- checks latest borrower/facility metrics against covenant thresholds
- writes breaches to `covenant_breaches`

Reporting:

- renders investor and internal updates from the reporting layer
- stores Markdown and HTML every run
- optionally writes PDF output when `weasyprint` is installed

## Honest tradeoffs

- The data sources are mock APIs hosted in the same local app.
- SQLite is used for convenience; production would likely use Postgres or a warehouse-backed reporting layer.
- APScheduler runs in-process; production would move scheduling into a job system or orchestrator.
- The dashboard is intentionally small and operational, not polished product UI.
- PDF generation is optional because `weasyprint` can require extra system libraries depending on the machine.
- The MCP server is intentionally narrow and local-first; it is not presented here as a general-purpose agent platform.

## Testing and CI

Run locally:

```bash
python -m pytest tests/ -v
```

CI:

- GitHub Actions runs pytest on Python 3.11 and 3.12
- CI also smoke-tests the MCP server startup path

## Project layout

```text
api/                  Flask blueprints for source APIs, reporting APIs, jobs, and dashboard
app/                  Config, logging, shared schema helpers
db/                   SQLAlchemy models, session, init, and seed data
dedupe/               Deterministic dedupe rules
examples/             Real-ish adapter examples for moving beyond mock sources
jobs/                 APScheduler setup
mcp_server/           MCP stdio server
reports/              Generated report outputs
scripts/              Seed and one-shot sync helpers
services/             Sync orchestration, reconciliation, covenant, dashboard, reports
templates/            Dashboard UI
tests/                Unit and integration tests
validators/           Row-level and batch-level validation rules
```

## How this maps to private credit ops

- CRM pipeline tracking maps to deal and borrower records pulled from the mock CRM API.
- Fund admin reconciliation maps to a post-load comparison between reporting-layer records and a second source of position data.
- Covenant monitoring maps to threshold checks against latest operating metrics.
- Investor reporting maps to generated updates produced from normalized data rather than directly from source APIs.
- Agent support maps to the MCP layer, which makes the reporting store queryable from a tool-capable assistant.

## If you want to make this less demo-like

The next practical steps would be:

1. Replace the mock CRM adapter with a live integration against Salesforce, HubSpot, or DealCloud.
2. Replace the mock fund admin API with a file or API ingest path from the actual admin source.
3. Move scheduling out of the Flask process.
4. Add auth and secret management.
5. Add a second integration test path against captured real payload fixtures.
