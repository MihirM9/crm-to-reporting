![CI](https://github.com/MihirM9/crm-to-reporting/actions/workflows/ci.yml/badge.svg)

# CRM-to-Reporting for Private Credit

A small app that takes messy borrower data from a CRM, cleans it, checks it against the fund administrator's numbers, flags covenant breaches, and writes an investor update — automatically.

This is a demo, not a live system. The data sources are mocked so you can run it on a laptop in under a minute.

## What it does

Every time you run it, the app:

1. **Pulls** borrower and deal records from a mock CRM.
2. **Checks** each row for missing fields, bad dates, duplicate IDs, and other junk.
3. **Quarantines** the bad rows so they don't pollute reporting, but keeps them visible for review.
4. **Compares** the CRM's numbers (valuations, stages) against the fund admin's numbers and flags any mismatches.
5. **Checks** each borrower's latest metrics against their covenant thresholds (min EBITDA margin, max leverage, etc.) and flags breaches.
6. **Writes** an investor update and an internal ops update — Markdown, HTML, and optional PDF.

Everything above also works through a conversational agent interface, so you (or a PM) can just type *"Which borrowers tripped covenants this quarter?"* instead of clicking around.

## Why this matters for a private credit shop

Most middle-office time gets burned on four things:

- Chasing borrower data that arrived in a bad format
- Reconciling CRM deal records against the fund admin's position file
- Monitoring covenant compliance across a growing portfolio
- Assembling the investor letter every quarter

This app does all four in one pass, leaves an audit trail, and exposes the same data to an AI agent so a deal team can ask questions in natural language.

## Try it in 60 seconds

```bash
git clone https://github.com/MihirM9/crm-to-reporting
cd crm-to-reporting
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_demo.py
python main.py
```

Then open **http://127.0.0.1:8000** in your browser.

Click **Run Sync** in the top right. You'll see borrowers load, covenant breaches flag (Pinnacle Fintech trips its EBITDA floor), a reconciliation break appear (Verdant Energy's valuation is $210M in the CRM but $195M at the fund admin), and an investor update get written.

## What you're looking at on the dashboard

| Section | What's there |
|---|---|
| **Dashboard** | Top-line counts: how many records, how many breaks, how many breaches |
| **CRM Source** | The raw borrower data, including the intentionally bad rows |
| **Reporting Layer** | The clean, deduped version after validation |
| **Sync Runs** | Audit log of every run — what came in, what got rejected, how long it took |
| **Rejected Records** | Every bad row with a human-readable reason (so nothing gets silently dropped) |
| **Reconciliation** | CRM vs. fund admin mismatches, with severity |
| **Covenant Breaches** | Borrowers tripping their financial covenants |
| **Reports** | Generated investor and internal updates, click to read |
| **API** | The underlying endpoints, in case you want to hit them directly |

## The agent interface (the interesting part)

The same data is exposed to Claude as a set of tools. In a second terminal:

```bash
claude
```

Then try:

- *"Run the sync and tell me what got rejected."*
- *"Show me reconciliation breaks for Verdant Energy."*
- *"Which borrowers tripped covenants?"*
- *"Read me the latest investor update."*

Each of those invokes a real tool against the live reporting layer — not a chatbot reading a static summary.

## What's real vs. mocked

**Real:** the validation logic, the reconciliation logic, the covenant checks, the report generation, the agent tools, and the tests.

**Mocked:** the CRM itself (so you don't need Salesforce credentials), the fund admin feed, and the borrower data.

To point this at a real CRM, you'd swap one adapter file (`examples/real_crm_adapter.py`) and leave the rest of the pipeline untouched. That's the whole design.

## Tests

```bash
python -m pytest tests/ -v
```

11 tests, all green. CI runs them on every push against Python 3.11 and 3.12.


