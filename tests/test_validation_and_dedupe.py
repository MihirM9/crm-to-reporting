from dedupe.rules import metric_dedupe_key
from validators.rules import validate_company, validate_metric


def test_company_validation_rejects_missing_fields():
    result = validate_company({"external_id": "COMP-1", "name": "", "owner": None, "stage": "oops", "reporting_period": None})
    assert not result.is_valid
    assert "Missing required field: company name" in result.reasons
    assert "Invalid company stage: oops" in result.reasons


def test_metric_validation_rejects_non_numeric_values():
    result = validate_metric({"company_external_id": "COMP-1", "reporting_period": "2026-Q1", "revenue": "oops"})
    assert not result.is_valid
    assert "Invalid revenue: expected numeric value" in result.reasons


def test_metric_dedupe_key_prefers_external_id():
    assert metric_dedupe_key("MET-1", "Northstar", "2026-Q1") == "MET-1"


def test_metric_dedupe_key_falls_back_to_name_period():
    assert metric_dedupe_key(None, "Northstar Health", "2026-Q1") == "northstarhealth::2026-Q1"
