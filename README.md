![CI](https://github.com/MihirM9/crm-to-reporting/actions/workflows/ci.yml/badge.svg)

# CRM-to-Reporting Automation for Private Credit

A working reference implementation of the data pipeline a private credit fund's middle office actually needs: **multi-source reconciliation**, **automated covenant compliance**, and an **MCP agent layer** so a portfolio manager can query live data conversationally instead of opening dashboards.

## What it does

1. **Pulls borrower data** from a CRM source (deal flow, portfolio companies, covenant KPIs, quarterly updates) and a **mock fund admin** (SS&C / Citco-shaped position records) over REST.
2. **Cleans it** — validates, deduplicates, quarantines bad rows, and upserts idempotently into a reporting layer that downstream systems (fund admin reconciliation, LP portal, watchlist reviews) can trust.
3. **Reconciles CRM vs fund admin** — diffs valuations and stages between the two sources, classifies breaks by severity, and writes them to an auditable `reconciliation_breaks` table.
4. **Checks covenant compliance** — evaluates facility-level covenants (min EBITDA margin, max leverage, max burn multiple) against the latest borrower metrics and flags breaches.
5. **Auto-drafts reports** — quarterly investor update and internal ops update, templated from clean data, output as Markdown + HTML (+ PDF if weasyprint is installed).
6. **Exposes everything as an MCP server** — 13 agent-callable tools so Claude Code (or any MCP client) can trigger syncs, query borrowers, surface the credit watchlist, review reconciliation breaks, check covenant breaches, and read LP letters — no SQL, no dashboards needed.

---

## Architecture

```
 ┌──────────────────┐   ┌───────────────────┐
 │   Mock CRM API   │   │ Mock Fund Admin   │
 │ /api/mock-crm/*  │   │ /api/mock-admin/* │
 │ (companies,      │   │ (positions with   │
 │  deals, metrics, │   │  valuations,      │
 │  updates,        │   │  stages,          │
 │  contacts)       │   │  balances)        │
 └────────┬─────────┘   └────────┬──────────┘
          │      REST            │
          ▼                      ▼
 ┌─────────────────────────────────────────────┐
 │  Sync Service                               │
 │  • incremental, checkpointed                │
 │  • retries with exponential backoff         │
 │  • row-level validation + batch checks      │
 │  • deterministic dedupe                     │
 │  • idempotent upserts                       │
 │  • quarantines bad rows to rejected_records │
 └───────┬────────────────────┬────────────────┘
         │                    │
         ▼                    ▼
 ┌──────────────────┐  ┌──────────────────────┐
 │ Reporting Layer  │  │ rejected_records     │
 │ • borrowers      │  │ (quarantine + raw)   │
 │ • facilities     │  └──────────────────────┘
 │ • covenant KPIs  │
 │ • updates        │
 │ • sync_runs      │
 └──────┬───────────┘
        │
  ┌─────┴──────────────────────────────────┐
  │                                        │
  ▼                                        ▼
 ┌─────────────────────┐  ┌──────────────────────────────┐
 │ Post-Sync Checks    │  │ Report Generator             │
 │ • Reconciliation    │  │ Investor + Internal MD/HTML  │
 │   (CRM vs Admin)    │  │ + PDF (optional, weasyprint) │
 │ • Covenant breach   │  └──────────┬───────────────────┘
 │   detection         │             │
 └──────┬──────────────┘             ▼
        │                   Flask Dashboard + REST API
        ▼                   (Chart.js sync history)
 ┌──────────────────────────┐
 │ MCP Server (stdio)       │
 │ 13 tools — run_sync,     │
 │ list_borrowers,          │
 │ list_reconciliation_     │
 │   breaks,                │
 │ list_covenant_breaches,  │
 │ list_watchlist, etc.     │
 └──────────────────────────┘
        ▼
  Claude Code / any MCP client
```

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Seed the demo DB + run a sync
python scripts/seed_demo.py
python scripts/run_sync_once.py

# Launch the dashboard
python main.py
# → open http://127.0.0.1:8000
```

That gets you:
- A seeded SQLite DB with 10 borrowers, 6 facilities, 8 covenant KPI records, 5 quarterly updates, 5 fund admin positions (with intentional discrepancies), and 6 facility covenants.
- A dashboard showing sync runs, pipeline health, reconciliation breaks, covenant breaches, the reporting layer, rejected rows, and auto-generated reports.
- A sync history chart (Chart.js) visualizing inserted/updated/rejected counts across runs.
- A scheduled sync running every 3 minutes, plus manual trigger via button or `POST /api/jobs/run-sync`.

### PDF reports (optional)

```bash
pip install weasyprint   # requires system libs — see weasyprint docs
```

If weasyprint is installed, PDF reports are generated alongside MD and HTML after each sync. If not, the system works fine without it — the import is guarded.

### Run the test suite

```bash
python -m pytest tests/ -v
# 10 passed
```

---

## The MCP layer

The point of this project is that **a portfolio manager should never need to open the dashboard**. They should be able to ask Claude Code:

> "Which borrowers are on the watch list this quarter?"
> "Any reconciliation breaks between CRM and fund admin?"
> "Are there covenant breaches I should know about?"
> "Pull the draft LP letter for last sync run."
> "Anything get rejected in the latest sync?"

…and get real answers from live data.

### Wiring it into Claude Code

Add to your project's `.mcp.json` (or `~/.claude/mcp.json` for global access):

```json
{
  "mcpServers": {
    "crm-reporting": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/this/repo"
    }
  }
}
```

### Tools exposed

| Tool | Purpose (in private credit terms) |
|---|---|
| `run_sync` | Trigger a pull from CRM → reporting layer. |
| `get_latest_sync` | "Did our last reconciliation succeed?" |
| `list_sync_runs` | Full audit trail of every pipeline execution. |
| `list_borrowers` | Query cleaned portfolio companies, filter by stage / owner / period. |
| `list_facilities` | Query deal pipeline (sourced → IC → term_sheet → closed). |
| `get_kpi_movements` | Period-over-period revenue / margin / burn-multiple deltas per borrower. |
| `list_watchlist` | Auto-surfaced credit watchlist — negative EBITDA, burn > 2.0x, declining revenue. |
| `list_rejected_records` | Review quarantined rows — missing covenant data, bad types, invalid stages. |
| `list_reconciliation_breaks` | CRM vs fund admin recon diffs — valuation mismatches, stage disagreements. |
| `list_covenant_breaches` | Facility-level covenant violations with observed vs threshold values. |
| `list_reports` | List generated investor and internal updates. |
| `read_report` | Pull a full LP-letter draft into the conversation for editing. |
| `get_pipeline_stats` | One-shot pipeline health snapshot including recon + covenant counts. |

### Test it without Claude Code

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_watchlist","arguments":{}}}' \
  | python -m mcp_server.server
```

### Why hand-rolled instead of using the MCP SDK?

1. **Dependency hygiene.** MCP is just JSON-RPC 2.0 over newline-delimited stdio. Writing ~150 lines of it keeps the project installable anywhere Python runs, with no transitive pydantic/rpds-py wheel builds.
2. **Transparency.** Anyone reviewing this repo can read the whole protocol surface in one file (`mcp_server/server.py`).

---

## Project layout

```
api/                  Flask blueprints — mock CRM, mock fund admin, reporting, jobs, dashboard
services/             Sync orchestration, CRM client, reconciliation, covenant compliance, report generation
jobs/                 APScheduler background sync
validators/           Row-level + batch-level validation rules
dedupe/               Deterministic dedupe (external_id, composite key fallback)
db/                   SQLAlchemy models, session, schema init, seed data
reports/              Template outputs — generated MD + HTML + PDF reports
templates/            Flask dashboard (single-page, tabbed internal-ops UI with Chart.js)
mcp_server/           MCP stdio server + 13 agent-callable tools
scripts/              Ops utilities (seed_demo, run_sync_once)
tests/                Unit tests + integration tests (including MCP tool coverage)
app/                  Config (.env loader), logging, shared schemas
main.py               Flask entry point (bootstraps data, starts scheduler)
.github/workflows/    CI — pytest on Python 3.11 & 3.12 for every push and PR
```

---

## Core behaviors

- **Multi-source ingestion.** CRM source + fund admin source, reconciled post-sync.
- **Incremental sync with checkpoints.** `sync_runs.checkpoint_ended_at` carries forward so re-runs don't re-fetch the world.
- **Idempotent upserts.** All reporting tables unique on `external_id` (or composite dedupe key for metrics). Safe to replay any run.
- **Retries with exponential backoff.** `services/crm_client.py` retries 5xx / connection errors up to `CRM_API_MAX_RETRIES`.
- **Row-level validation.** Missing required fields, bad types, invalid enums → quarantined to `rejected_records` with raw payload + human-readable reason.
- **Batch-level checks.** Zero-row pulls, null-heavy datasets, abnormal row-count deltas → surfaced as run warnings.
- **Fund admin reconciliation.** Post-sync diff of CRM vs fund admin on valuation, stage, and other fields. Breaks classified as info/warning/critical and persisted for audit.
- **Covenant compliance.** Facility covenants (min EBITDA margin, max leverage, max burn multiple) evaluated against latest metrics. Breaches recorded with observed vs threshold values.
- **Run-level metrics.** `sync_runs` captures extracted / transformed / inserted / updated / rejected / duration / warnings for every execution.
- **Structured logging.** JSON logs on stderr with `event` + `context` tags.
- **Report generation.** After each successful sync, investor and internal templates render to MD + HTML (+ PDF if weasyprint is installed), now enriched with reconciliation + covenant breach sections.
- **Continuous integration.** GitHub Actions runs the pytest suite on Python 3.11 and 3.12 for every push and PR, and smoke-tests the MCP server subprocess.

---

## How this maps to real private credit workflows

| Private credit workflow | Mapped feature |
|---|---|
| **Deal sourcing → IC → closing pipeline** tracked in DealCloud / Salesforce | `crm_deals` / `deal_pipeline` — stage enum mirrors a typical IC funnel |
| **Quarterly borrower compliance certificates** re-keyed by analysts | `crm_metrics` → `reporting_metrics`, with type validation |
| **Fund admin reconciliation** — quarterly CSV from SS&C / Citco | `reconciliation_service.py` diffs CRM vs fund admin, writes breaks |
| **Covenant compliance checks** before credit committee | `covenant_service.py` evaluates thresholds per facility |
| **Duplicate borrower records** from multiple deal teams | `dedupe/rules.py` — external_id primary, normalized composite fallback |
| **Quarterly LP letter** hand-written from spreadsheets | `report_service.py` — auto-drafted from clean data in MD + HTML + PDF |
| **Credit watchlist reviews** before PM meeting | `list_watchlist` MCP tool — flags borrowers with negative EBITDA, burn > 2.0x, or declining revenue |
| **"Why is Borrower X missing from Q1 numbers?"** | `rejected_records` + `list_rejected_records` — every quarantined row preserved with reason |
| **Audit / LP diligence on pipeline execution** | `sync_runs` + `list_sync_runs` — full trail with metrics |
| **PM asks a natural-language question** | MCP layer — 13 tools covering read + write operations |

---

## Configuration

Copy `.env.example` → `.env`:

```
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=sqlite:///./crm_reporting_demo.db
CRM_API_BASE_URL=http://127.0.0.1:8000/api/mock-crm
SYNC_INTERVAL_SECONDS=180
CRM_API_TIMEOUT_SECONDS=5
CRM_API_MAX_RETRIES=3
REPORT_OUTPUT_DIR=reports/generated
LOG_LEVEL=INFO
```

To point at a real CRM: swap `CRM_API_BASE_URL` and replace `CRMClient._request`. Nothing else needs to change.

---

## Tradeoffs and explicit non-goals

- **SQLite over Postgres** for the demo. SQLAlchemy makes Postgres a one-env-var swap.
- **In-process APScheduler** — production would externalize orchestration (Airflow, Prefect, Temporal).
- **Mock CRM + fund admin APIs** live in the same Flask app. Pointing at real sources is a base-URL change.
- **No auth** — intentional for readability. Production would sit behind SSO.
- **PDF output optional** — depends on weasyprint (C deps). System works without it.
- **Not a replacement** for a real middle/back office stack — it's a reference implementation of the *integration pattern*.
