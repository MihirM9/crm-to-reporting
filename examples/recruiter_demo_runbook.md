# Recruiter Demo Runbook

Use this if you want the demo to start empty, load one CSV, generate reporting outputs, and then let Claude Code query the results.

## 1. Start the app

```bash
source .venv/bin/activate
APP_PORT=8010 python main.py
```

Open `http://127.0.0.1:8010`.

## 2. Reset the demo and import the one-sheet CSV

From a second terminal:

```bash
source .venv/bin/activate
python scripts/load_recruiter_sheet.py examples/recruiter_demo_crm_sheet.csv
```

That command will:

- clear the existing demo data
- import the single recruiter CSV into the mock CRM tables
- run a sync
- generate fresh reports from the imported data

## 3. What should appear in the app

- CRM records populated from the uploaded sheet
- reporting-layer records after sync
- rejected records for intentionally bad rows
- generated investor/internal reports

## 4. How to use Claude Code / MCP on top of the imported data

This repo already includes MCP wiring in [.mcp.json](/Users/mihir/Downloads/CRM%20to%20Reporting/.mcp.json:1).

Once the data is imported and synced, Claude Code can use MCP tools against the same reporting layer.

Example prompts:

- "Run the latest sync and summarize rejected records."
- "List KPI movement for imported companies."
- "Show me the latest investor report."
- "Which rows were quarantined and why?"

## 5. One-line recruiter explanation

"The app starts empty, I load one CRM CSV, the pipeline syncs it into the reporting layer, quarantines bad rows, generates reports, and then Claude Code can query the same reporting data through MCP tools."
