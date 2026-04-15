from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ValidationResult:
    is_valid: bool
    reasons: list[str] = field(default_factory=list)
    normalized_record: dict[str, Any] | None = None


def paginated_response(data: list[dict[str, Any]], limit: int, offset: int, total: int) -> dict[str, Any]:
    next_offset = offset + limit if (offset + limit) < total else None
    return {
        "data": data,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(data),
            "total": total,
            "next_offset": next_offset,
        },
    }


def sync_summary_payload(sync_run: Any) -> dict[str, Any]:
    return {
        "sync_run_id": sync_run.id,
        "status": sync_run.status,
        "extracted_count": sync_run.extracted_count,
        "transformed_count": sync_run.transformed_count,
        "loaded_inserted_count": sync_run.loaded_inserted_count,
        "loaded_updated_count": sync_run.loaded_updated_count,
        "rejected_count": sync_run.rejected_count,
        "duration_ms": sync_run.duration_ms,
        "started_at": sync_run.started_at.isoformat() if isinstance(sync_run.started_at, datetime) else sync_run.started_at,
        "ended_at": sync_run.ended_at.isoformat() if sync_run.ended_at else None,
        "warnings": sync_run.warnings or [],
    }
