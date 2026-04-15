from __future__ import annotations

import re


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower().strip())


def metric_dedupe_key(external_id: str | None, company_name: str | None, reporting_period: str | None) -> str:
    if external_id:
        return external_id
    return f"{normalize_text(company_name)}::{reporting_period or 'unknown'}"
