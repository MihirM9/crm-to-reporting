# Private Credit Ops Automation — CRM to Reporting, with an MCP Layer

An AI-native operational spine for a private credit manager, built as a full-stack demo.

It does three things a middle-office team would otherwise do by hand:

1. **Pulls borrower data** from a CRM-shaped source (deal flow, portfolio companies, covenant KPIs, quarterly updates) over REST.
2. **Cleans it** — validates, deduplicates, quarantines bad rows, and upserts idempotently into a reporting layer that downstream systems (fund admin reconciliation, LP portal, watchlist reviews) can trust.
3. **Auto-drafts the outputs** a PM actually uses — a quarterly investor update and an internal ops update — templated from the latest clean data.

On top of that, it exposes the whole pipeline as an **MCP (Model Context Protocol) server**, so an agent like Claude Code can trigger syncs, query the reporting layer, surface a credit watchlist, and read generated LP letters conversationally — no SQL, no dashboards.

This repo is deliberately shaped around the workflows a private credit middle/back office actually runs. See **[How this maps to real private credit workflows](#how-this-maps-to-real-private-credit-workflows)** at the bottom.

---

## Why this exists

Private credit firms sit on top of a familiar stack — CRM (HubSpot / DealCloud / Salesforce), a fund admin (SS&C, Citco, Alter Domus), a portfolio monitoring system, and an LP portal. Every quarter, somebody manually:

- Pulls borrower financials out of the CRM and reconciles them against what fund admin has on file.
- Chases missing covenant compliance certificates from portfolio companies.
- Identifies which borrowers are drifting into a credit watch zone.
- Writes the quarterly LP letter from a pile of spreadsheets.

All of that is API-shaped and automatable. This project is a working reference implementation of the "cleaned data lake + agent-callable tools" pattern that makes it possible.

---

## Architecture at a glance

```
 ┌──────────────────┐          ┌─────────────────────────────────┐
 │   Mock CRM API   │  REST    │  Sync Service                   │
 │ /api/mock-crm/*  │ ───────▶ │  • incremental, checkpointed    │
 │ (companies,      │          │  • retries with backoff         │
 │  deals, metrics, │          │  • validates each row           │
 │  updates,        │          │  • dedupes deterministically    │
 │  contacts)       │          │  • quarantines bad rows         │
 └──────────────────┘          │  • idempotent upserts           │
                               └──────┬──────────────────┬───────┘
                                      │                  │
                                      ▼                  ▼
                        ┌──────────────────┐  ┌──────────────────┐
                        │ Reporting Layer  │  │ rejected_records │
                        │ • borrowers      │  │ (quarantine +    │
                        │ • facilities     │  │  raw payload)    │
                        │ • covenant KPIs  │  └──────────────────┘
                        │ • updates        │
                        │ • sync_runs      │
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
       ┌────────────────────┐     ┌────────────────────────┐
       │ Report Generator   │     │ MCP Server (stdio)     │
       │ Investor + Internal│     │ 11 tools — run_sync,   │
       │ MD + HTML, templated│    │ list_borrowers,        │
       │                    │     │ list_watchlist, etc.   │
       └─────────┬──────────┘     └──────────┬─────────────┘
                 │                           │
                 ▼                           ▼
          Flask Dashboard              Claude Code / any
          + REST API                   MCP-aware client
```

---

## Quick start

```bash
# Clone and install
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
- A seeded SQLite DB with 10 borrowers, 6 facilities, 8 covenant KPI records, 5 quarterly updates (with intentionally broken rows so validation and quarantine are visible).
- A dashboard showing sync runs, pipeline health, the reporting layer, rejected rows, and auto-generated reports — all in one internal-ops-style UI.
- A scheduled sync running every 3 minutes, plus manual trigger via button or `POST /api/jobs/run-sync`.

Run the test suite:

```bash
python -m pytest tests/ -v
# 10 passed
```

---

## The MCP layer — the piece a PM actually uses

Running the dashboard is fine for a demo. The point of this project is that **a portfolio manager should never need to open the dashboard**. They should be able to ask Claude Code:

> "Which borrowers are on the watch list this quarter?"
> "Pull the draft LP letter for last sync run."
> "Anything get rejected in the latest sync?"
> "Show me revenue movement across the portfolio."

…and get real answers from live data. That's what the MCP server provides.

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

Claude Code will spawn the server on startup and list its tools automatically.

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
| `list_reports` | List generated investor and internal updates. |
| `read_report` | Pull a full LP-letter draft into the conversation for editing. |
| `get_pipeline_stats` | One-shot pipeline health snapshot. |

### Test it without Claude Code

The MCP server speaks plain JSON-RPC over stdio — you can drive it from a shell:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_watchlist","arguments":{}}}' \
  | python -m mcp_server.server
```

### Why hand-rolled instead of using the MCP SDK?

Two reasons:
1. **Dependency hygiene.** MCP is just JSON-RPC 2.0 over newline-delimited stdio. Writing ~120 lines of it keeps the project installable anywhere Python runs, with no transitive pydantic/rpds-py wheel builds.
2. **Transparency.** Anyone reviewing this repo can read the whole protocol surface in one file (`mcp_server/server.py`) instead of chasing SDK layers. Useful when the reviewer's job is evaluating whether you actually understand agent integration.

---

## Project layout

```
api/                  Flask blueprints — mock CRM, reporting, jobs, dashboard
services/             Sync orchestration, CRM client, report generation, dashboard context
jobs/                 APScheduler background sync
validators/           Row-level + batch-level validation rules
dedupe/               Deterministic dedupe (external_id, composite key fallback)
db/                   SQLAlchemy models, session, schema init, seed data
reports/              Template outputs — generated MD + HTML reports live under reports/generated/
templates/            Flask dashboard (single-page, tabbed internal-ops UI)
mcp_server/           MCP stdio server + 11 agent-callable tools
scripts/              Ops utilities (seed_demo, run_sync_once)
tests/                Unit tests + integration tests (including MCP tool coverage)
app/                  Config (.env loader), logging, shared schemas
main.py               Flask entry point (bootstraps data, starts scheduler)
```

---

## Core behaviors (per the original spec)

- **Incremental sync with checkpoints.** `sync_runs.checkpoint_ended_at` carries forward so re-runs don't re-fetch the world.
- **Idempotent upserts.** All reporting tables unique on `external_id` (or composite dedupe key for metrics). Safe to replay any run.
- **Retries with exponential backoff.** `services/crm_client.py` retries 5xx / connection errors up to `CRM_API_MAX_RETRIES`.
- **Row-level validation.** Missing required fields, bad types, invalid enums → quarantined to `rejected_records` with raw payload + human-readable reason.
- **Batch-level checks.** Zero-row pulls, null-heavy datasets, abnormal row-count deltas → surfaced as run warnings (not failures).
- **Run-level metrics.** `sync_runs` captures extracted / transformed / inserted / updated / rejected / duration / warnings for every execution.
- **Structured logging.** JSON logs on stderr with `event` + `context` tags.
- **Scheduled + manual triggers.** APScheduler runs every `SYNC_INTERVAL_SECONDS` (default 180s). Manual trigger via `POST /api/jobs/run-sync`, the dashboard button, or the `run_sync` MCP tool.
- **Report generation.** After each successful sync, both investor and internal templates render to both markdown and HTML, saved under `reports/generated/` and exposed via `/api/reporting/reports`.

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

To point at a real CRM: swap `CRM_API_BASE_URL` and replace the thin `CRMClient._request` method. Nothing else needs to change — the sync service is decoupled from the source.

---

## How this maps to real private credit workflows

| Private credit workflow | Mapped feature in this repo |
|---|---|
| **Deal sourcing → IC → closing pipeline** tracked in DealCloud / Salesforce | `crm_deals` / `deal_pipeline` — stage enum mirrors a typical IC funnel (sourced → screening → ic → term_sheet → closed_won/lost) |
| **Quarterly borrower compliance certificates** (revenue, EBITDA margin, leverage / burn proxies) re-keyed by analysts | `crm_metrics` → `reporting_metrics`, with type validation catching the "Excel dumped the value as a string" problem |
| **Duplicate borrower records** from multiple deal teams entering the same name with slight variations | `dedupe/rules.py` — external_id primary, normalized name + reporting period composite key fallback |
| **Fund admin reconciliation** — quarterly CSV from SS&C / Citco that doesn't match internal CRM | The sync service's idempotent upsert pattern is how you'd reconcile without double-counting |
| **Quarterly LP letter** hand-written in Word from a pile of spreadsheets | `report_service.py` — templated investor update in MD + HTML, auto-drafted from the latest clean data |
| **Credit watchlist reviews** before a weekly PM meeting | `list_watchlist` MCP tool — flags borrowers with negative EBITDA, burn > 2.0x, or declining revenue |
| **"Why is Borrower X missing from my Q1 numbers?"** | `rejected_records` table + `list_rejected_records` MCP tool — every quarantined row preserved with reason and raw payload, not silently dropped |
| **Audit / LP diligence asking for pipeline execution history** | `sync_runs` + `list_sync_runs` — full trail with metrics, status, duration, warnings |
| **PM wants to ask a natural-language question instead of opening a dashboard** | MCP layer — 11 agent-callable tools covering read + write operations |

---

## Tradeoffs and explicit non-goals

- **SQLite over Postgres** for the demo. The SQLAlchemy layer makes Postgres a one-env-var swap.
- **In-process APScheduler** — production would externalize orchestration (Airflow, Prefect, Temporal) with retry policies and alerting.
- **Mock CRM API** lives at `/api/mock-crm/*` in the same Flask app. Pointing at a real CRM is a base-URL change plus swapping the request method if auth differs.
- **No auth** — intentional, to keep the demo readable. A real deployment would sit behind a reverse proxy with SSO.
- **No PDF output** for reports. MD + HTML only; adding PDF is a one-library change (weasyprint / xhtml2pdf) on top of the existing HTML template.
- **Not a replacement** for a real middle/back office stack — it's a reference implementation of the *integration pattern*, not a shipping product.
