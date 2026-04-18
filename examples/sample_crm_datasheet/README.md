# Sample CRM Datasheet Pack

This folder contains a recruiter-friendly sample CRM data pack that matches the demo's mock CRM schema.

Use it when you want someone to:

- understand the fields expected by the CRM-to-reporting pipeline
- test a "happy path" CRM export
- see what kinds of bad rows should be rejected or quarantined

## Included folders

- `clean/`: realistic sample CRM exports that should pass validation
- `edge_cases/`: intentionally problematic rows for validation, dedupe, and quarantine testing

## Files

- `crm_companies.csv`
- `crm_contacts.csv`
- `crm_deals.csv`
- `crm_metrics.csv`
- `crm_updates.csv`

## Notes

- Date-time fields use ISO-8601 format like `2026-04-17T09:30:00`.
- Valid company stages:
  - `new`
  - `qualified`
  - `portfolio`
  - `monitoring`
  - `realized`
- Valid deal stages:
  - `sourced`
  - `screening`
  - `ic`
  - `term_sheet`
  - `closed_won`
  - `closed_lost`
- Valid update types:
  - `investor`
  - `internal`
  - `portfolio`

## Recommended recruiter demo flow

1. Review the `clean/` files first to understand the expected CRM export shape.
2. Compare the rows to the dashboard sections:
   - companies map into reporting companies
   - deals map into deal pipeline
   - metrics drive KPI movement and covenant/recon checks
   - updates feed investor and internal reports
3. Review the `edge_cases/` files to see examples that should:
   - dedupe on `external_id`
   - fail validation due to missing required fields
   - fail validation due to invalid stage or malformed KPI values
   - remain quarantined instead of breaking the whole sync

## Field expectations by entity

### Companies

- `external_id`
- `name`
- `owner`
- `stage`
- `reporting_period`
- `valuation`
- `updated_at`
- `source_system`
- `status`

### Contacts

- `external_id`
- `company_external_id`
- `full_name`
- `email`
- `owner`
- `updated_at`
- `source_system`

### Deals

- `external_id`
- `company_external_id`
- `name`
- `stage`
- `owner`
- `amount`
- `updated_at`
- `source_system`

### Metrics

- `external_id`
- `company_external_id`
- `reporting_period`
- `revenue`
- `ebitda_margin`
- `burn_multiple`
- `updated_at`
- `source_system`

### Updates

- `external_id`
- `company_external_id`
- `reporting_period`
- `update_type`
- `summary`
- `updated_at`
- `source_system`
