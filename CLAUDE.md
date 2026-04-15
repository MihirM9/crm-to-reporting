# CLAUDE.md — Agent onboarding for this repo

Context for agents (Claude Code and similar) working in this project.

## What this is

An AI-native operational automation demo for a private credit manager. It syncs CRM-shaped source data into a cleaned reporting layer, generates investor/internal reports, and exposes the whole pipeline as an MCP server so agents can drive it conversationally.

Key vocabulary: companies = **borrowers**, deals = **facilities**, metrics = **covenant KPIs**, updates = **quarterly borrower updates** / **LP letter inputs**. The schema uses the generic names; surface language (docs, MCP tool descriptions, reports) uses the private-credit names.

## Where things live

- `api/` — Flask blueprints. Mock CRM at `/api/mock-crm/*`, reporting at `/api/reporting/*`, sync jobs at `/api/jobs/*`, dashboard at `/`.
- `services/sync_service.py` — the ETL orchestrator. Everything important about validation, dedupe, idempotent upserts, and quarantine happens here. Read this first.
- `services/crm_client.py` — HTTP client with retries/backoff. Swap `_request` to integrate a real CRM.
- `services/report_service.py` — Jinja2 templates for investor + internal reports.
- `mcp_server/server.py` — hand-rolled MCP stdio server (JSON-RPC 2.0 over newline-delimited stdio). 11 tools registered in `TOOLS`. No external MCP SDK dependency.
- `validators/rules.py` — row-level + batch-level validation. Add new rules here, not inline in sync.
- `dedupe/rules.py` — deterministic dedupe keys.
- `db/models.py` — SQLAlchemy schema. All timestamps are naive UTC.
- `db/seed_data.py` — demo data with **intentional** bad rows (missing fields, bad types, invalid stages, duplicates). Keep those on purpose — they're how we demonstrate validation/quarantine.
- `tests/` — pytest. `test_mcp_server.py` patches `CRMClient` via monkeypatch to drive the mock CRM through Flask's test client.

## Running

```bash
source .venv/bin/activate        # Python 3.15 alpha, don't upgrade pydantic-dependent libs
python main.py                   # dashboard at http://127.0.0.1:8000
python -m mcp_server.server      # MCP stdio server (use from Claude Code via .mcp.json)
python -m pytest tests/ -v       # 10 tests, should all pass
```

## Style rules

- `from __future__ import annotations` at the top of every Python file.
- Structured JSON logs via `logger.info("event", extra={"event": ..., "context": ...})`. Never print to stdout from library code — stdout is reserved for the MCP server's JSON-RPC frames.
- The MCP server logs to **stderr only**. If you add tools, don't print anything.
- Sync service failures must not kill a run — one bad record goes to `rejected_records`, not an exception.
- All reporting-layer writes must be idempotent. Check before you insert.
- Don't add new dependencies without a strong reason. `mcp_server/` exists without the MCP SDK on purpose.

## Adding a new MCP tool

1. Write a handler in `mcp_server/server.py`: `def tool_foo(args: dict) -> dict:` — returns a JSON-serializable dict.
2. Append an entry to the `TOOLS` list with `name`, `description` (private-credit framed), `inputSchema`, and `handler`.
3. Add a test in `tests/test_mcp_server.py` using the `handle_request(...)` entry point (no subprocess needed).
4. Update the tools table in `README.md`.

## Things to not do

- Don't bypass `rejected_records` — silently dropping bad rows is the anti-pattern this repo exists to demonstrate against.
- Don't break idempotency. Always upsert on `external_id` (or composite dedupe key).
- Don't hardcode the CRM base URL. It comes from `app.config.get_settings().crm_api_base_url`.
- Don't introduce timezone-aware datetimes. The models are naive UTC throughout.
