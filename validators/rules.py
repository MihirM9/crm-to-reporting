from __future__ import annotations

from typing import Any

from app.schemas import ValidationResult


VALID_DEAL_STAGES = {"sourced", "screening", "ic", "term_sheet", "closed_won", "closed_lost"}
VALID_COMPANY_STAGES = {"new", "qualified", "portfolio", "monitoring", "realized"}
VALID_UPDATE_TYPES = {"investor", "internal", "portfolio"}


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_company(record: dict[str, Any]) -> ValidationResult:
    reasons: list[str] = []
    if _is_blank(record.get("external_id")):
        reasons.append("Missing required field: external_id")
    if _is_blank(record.get("name")):
        reasons.append("Missing required field: company name")
    if _is_blank(record.get("owner")):
        reasons.append("Missing required field: owner")
    if _is_blank(record.get("stage")):
        reasons.append("Missing required field: stage")
    elif record["stage"] not in VALID_COMPANY_STAGES:
        reasons.append(f"Invalid company stage: {record['stage']}")
    if _is_blank(record.get("reporting_period")):
        reasons.append("Missing required field: reporting_period")
    valuation = record.get("valuation")
    if valuation is not None and not isinstance(valuation, (int, float)):
        reasons.append("Invalid valuation: expected numeric value")
    return ValidationResult(is_valid=not reasons, reasons=reasons, normalized_record=record if not reasons else None)


def validate_deal(record: dict[str, Any]) -> ValidationResult:
    reasons: list[str] = []
    for field_name in ("external_id", "name", "stage", "owner"):
        if _is_blank(record.get(field_name)):
            reasons.append(f"Missing required field: {field_name}")
    if record.get("stage") and record["stage"] not in VALID_DEAL_STAGES:
        reasons.append(f"Invalid deal stage: {record['stage']}")
    amount = record.get("amount")
    if amount is not None and not isinstance(amount, (int, float)):
        reasons.append("Invalid amount: expected numeric value")
    return ValidationResult(is_valid=not reasons, reasons=reasons, normalized_record=record if not reasons else None)


def validate_metric(record: dict[str, Any]) -> ValidationResult:
    reasons: list[str] = []
    for field_name in ("company_external_id", "reporting_period"):
        if _is_blank(record.get(field_name)):
            reasons.append(f"Missing required field: {field_name}")
    for numeric_field in ("revenue", "ebitda_margin", "burn_multiple"):
        value = record.get(numeric_field)
        if value is not None and not isinstance(value, (int, float)):
            reasons.append(f"Invalid {numeric_field}: expected numeric value")
    return ValidationResult(is_valid=not reasons, reasons=reasons, normalized_record=record if not reasons else None)


def validate_update(record: dict[str, Any]) -> ValidationResult:
    reasons: list[str] = []
    for field_name in ("external_id", "company_external_id", "reporting_period", "summary"):
        if _is_blank(record.get(field_name)):
            reasons.append(f"Missing required field: {field_name}")
    update_type = record.get("update_type")
    if _is_blank(update_type):
        reasons.append("Missing required field: update_type")
    elif update_type not in VALID_UPDATE_TYPES:
        reasons.append(f"Invalid update_type: {update_type}")
    return ValidationResult(is_valid=not reasons, reasons=reasons, normalized_record=record if not reasons else None)


def run_batch_checks(entity_name: str, records: list[dict[str, Any]], previous_count: int | None) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if not records:
        warnings.append({"entity": entity_name, "type": "zero_row_pull", "message": "No records returned for this entity."})
        return warnings

    null_heavy = 0
    for record in records:
        values = list(record.values())
        if values:
            null_ratio = sum(1 for value in values if value in (None, "")) / len(values)
            if null_ratio > 0.4:
                null_heavy += 1
    if null_heavy / len(records) > 0.3:
        warnings.append(
            {
                "entity": entity_name,
                "type": "excessive_null_rate",
                "message": "More than 30% of records have over 40% null or blank fields.",
            }
        )

    if previous_count and previous_count > 0:
        ratio = len(records) / previous_count
        if ratio < 0.5 or ratio > 1.5:
            warnings.append(
                {
                    "entity": entity_name,
                    "type": "abnormal_row_count_change",
                    "message": f"Row volume changed materially versus prior run: current={len(records)} prior={previous_count}",
                }
            )

    return warnings
