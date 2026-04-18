Subject: CRM-to-Reporting demo sample data

Hi [Recruiter Name],

I attached one simple CSV called `recruiter_demo_crm_sheet.csv` for the CRM-to-reporting automation demo.

How to read it:

- `entity_type` tells you what kind of CRM row it is: `company`, `contact`, `deal`, `metric`, or `update`
- `linked_company_external_id` ties contacts, deals, metrics, and updates back to a company
- most rows are valid and should flow through the sync normally
- a few rows are intentionally bad so you can see validation, dedupe, and quarantine behavior

What the demo should show:

- valid CRM rows syncing into the reporting layer
- one duplicate row getting deduped
- invalid rows getting rejected with human-readable reasons
- KPI movement and updates feeding the generated investor/internal reports

The intentionally bad rows are labeled in the `test_note` column so you don’t have to guess what should happen.

Best,
[Your Name]
