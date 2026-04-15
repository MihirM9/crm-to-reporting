from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import DealPipeline, GeneratedReport, RejectedRecord, ReportingCompany, ReportingMetric, ReportingUpdate, SyncRun
from dedupe.rules import metric_dedupe_key
from services.crm_client import CRMClient
from services.report_service import generate_reports
from validators.rules import run_batch_checks, validate_company, validate_deal, validate_metric, validate_update


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


Validator = Callable[[dict[str, Any]], Any]


class SyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.crm_client = CRMClient()

    def _previous_successful_run(self) -> SyncRun | None:
        return self.db.scalar(select(SyncRun).where(SyncRun.status == "success").order_by(SyncRun.started_at.desc()))

    def run_sync(self, trigger_mode: str = "manual") -> SyncRun:
        previous_run = self._previous_successful_run()
        sync_run = SyncRun(trigger_mode=trigger_mode, status="running", checkpoint_started_from=previous_run.checkpoint_ended_at if previous_run else None)
        self.db.add(sync_run)
        self.db.commit()
        self.db.refresh(sync_run)

        started = perf_counter()
        warnings: list[dict[str, Any]] = []

        try:
            entities = [
                ("companies", validate_company, self._load_company),
                ("deals", validate_deal, self._load_deal),
                ("metrics", validate_metric, self._load_metric),
                ("updates", validate_update, self._load_update),
            ]
            transformed_count = 0
            inserted_count = 0
            updated_count = 0
            rejected_count = 0
            extracted_count = 0

            for entity_name, validator, loader in entities:
                previous_count = self._entity_record_count(entity_name)
                records = self.crm_client.fetch_incremental(entity_name, sync_run.checkpoint_started_from)
                extracted_count += len(records)
                warnings.extend(run_batch_checks(entity_name, records, previous_count))

                deduped_records, deduped_count = self._dedupe_records(entity_name, records)
                if deduped_count:
                    warnings.append(
                        {
                            "entity": entity_name,
                            "type": "dedupe_applied",
                            "message": f"Removed {deduped_count} duplicate source rows using deterministic dedupe rules.",
                        }
                    )
                for record in deduped_records:
                    validation = validator(record)
                    if not validation.is_valid:
                        rejected_count += 1
                        self._quarantine(sync_run.id, entity_name, record, "; ".join(validation.reasons), {"reasons": validation.reasons})
                        continue
                    transformed_count += 1
                    load_result = loader(validation.normalized_record, sync_run.id)
                    if load_result == "inserted":
                        inserted_count += 1
                    else:
                        updated_count += 1

            sync_run.status = "success"
            sync_run.extracted_count = extracted_count
            sync_run.transformed_count = transformed_count
            sync_run.loaded_inserted_count = inserted_count
            sync_run.loaded_updated_count = updated_count
            sync_run.rejected_count = rejected_count
            sync_run.warnings = warnings
            sync_run.checkpoint_ended_at = utcnow()
            sync_run.ended_at = utcnow()
            sync_run.duration_ms = int((perf_counter() - started) * 1000)
            sync_run.status_message = "Sync completed successfully."

            self.db.flush()
            reports = generate_reports(self.db, sync_run)
            for report in reports:
                self.db.add(report)

            self.db.commit()
            self.db.refresh(sync_run)

            logger.info("Sync completed", extra={"event": "sync_completed", "context": {"sync_run_id": sync_run.id}})
            return sync_run
        except Exception as exc:
            self.db.rollback()
            sync_run.status = "failed"
            sync_run.ended_at = utcnow()
            sync_run.duration_ms = int((perf_counter() - started) * 1000)
            sync_run.status_message = str(exc)
            sync_run.warnings = warnings
            self.db.add(sync_run)
            self.db.commit()
            logger.exception("Sync failed", extra={"event": "sync_failed", "context": {"sync_run_id": sync_run.id}})
            return sync_run

    def _entity_record_count(self, entity_name: str) -> int:
        lookup = {
            "companies": ReportingCompany,
            "deals": DealPipeline,
            "metrics": ReportingMetric,
            "updates": ReportingUpdate,
        }
        model = lookup[entity_name]
        return int(self.db.scalar(select(func.count()).select_from(model)) or 0)

    def _dedupe_records(self, entity_name: str, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        deduped: dict[str, dict[str, Any]] = {}
        for record in records:
            if entity_name == "metrics":
                key = metric_dedupe_key(record.get("external_id"), record.get("company_external_id"), record.get("reporting_period"))
            else:
                key = record.get("external_id") or f"{record.get('name')}::{record.get('reporting_period')}"
            current = deduped.get(key)
            if current is None or record.get("updated_at", "") > current.get("updated_at", ""):
                deduped[key] = record
        removed_count = len(records) - len(deduped)
        if removed_count > 0:
            logger.info(
                "Deduped source records",
                extra={"event": "dedupe", "context": {"entity": entity_name, "deduped_count": removed_count}},
            )
        return list(deduped.values()), removed_count

    def _quarantine(self, sync_run_id: int, entity_type: str, record: dict[str, Any], reason: str, details: dict[str, Any]) -> None:
        self.db.add(
            RejectedRecord(
                sync_run_id=sync_run_id,
                entity_type=entity_type,
                source_external_id=record.get("external_id"),
                reason=reason,
                details=details,
                raw_record=record,
            )
        )
        logger.warning(
            "Record quarantined",
            extra={"event": "record_quarantined", "context": {"sync_run_id": sync_run_id, "entity": entity_type, "reason": reason}},
        )

    def _load_company(self, record: dict[str, Any], sync_run_id: int) -> str:
        existing = self.db.scalar(select(ReportingCompany).where(ReportingCompany.external_id == record["external_id"]))
        if existing:
            existing.company_name = record["name"]
            existing.owner = record["owner"]
            existing.stage = record["stage"]
            existing.reporting_period = record["reporting_period"]
            existing.valuation = record.get("valuation")
            existing.source_system = record["source_system"]
            existing.crm_updated_at = datetime.fromisoformat(record["updated_at"])
            existing.last_sync_run_id = sync_run_id
            return "updated"
        self.db.add(
            ReportingCompany(
                external_id=record["external_id"],
                company_name=record["name"],
                owner=record["owner"],
                stage=record["stage"],
                reporting_period=record["reporting_period"],
                valuation=record.get("valuation"),
                source_system=record["source_system"],
                crm_updated_at=datetime.fromisoformat(record["updated_at"]),
                last_sync_run_id=sync_run_id,
            )
        )
        return "inserted"

    def _load_deal(self, record: dict[str, Any], sync_run_id: int) -> str:
        existing = self.db.scalar(select(DealPipeline).where(DealPipeline.external_id == record["external_id"]))
        if existing:
            existing.company_external_id = record.get("company_external_id")
            existing.deal_name = record["name"]
            existing.stage = record["stage"]
            existing.owner = record["owner"]
            existing.amount = record.get("amount")
            existing.source_system = record["source_system"]
            existing.crm_updated_at = datetime.fromisoformat(record["updated_at"])
            existing.last_sync_run_id = sync_run_id
            return "updated"
        self.db.add(
            DealPipeline(
                external_id=record["external_id"],
                company_external_id=record.get("company_external_id"),
                deal_name=record["name"],
                stage=record["stage"],
                owner=record["owner"],
                amount=record.get("amount"),
                source_system=record["source_system"],
                crm_updated_at=datetime.fromisoformat(record["updated_at"]),
                last_sync_run_id=sync_run_id,
            )
        )
        return "inserted"

    def _load_metric(self, record: dict[str, Any], sync_run_id: int) -> str:
        dedupe_key = metric_dedupe_key(record.get("external_id"), record.get("company_external_id"), record.get("reporting_period"))
        existing = self.db.scalar(select(ReportingMetric).where(ReportingMetric.dedupe_key == dedupe_key))
        if existing:
            existing.external_id = record.get("external_id")
            existing.company_external_id = record["company_external_id"]
            existing.reporting_period = record["reporting_period"]
            existing.revenue = record.get("revenue")
            existing.ebitda_margin = record.get("ebitda_margin")
            existing.burn_multiple = record.get("burn_multiple")
            existing.source_system = record["source_system"]
            existing.crm_updated_at = datetime.fromisoformat(record["updated_at"])
            existing.last_sync_run_id = sync_run_id
            return "updated"
        self.db.add(
            ReportingMetric(
                dedupe_key=dedupe_key,
                external_id=record.get("external_id"),
                company_external_id=record["company_external_id"],
                reporting_period=record["reporting_period"],
                revenue=record.get("revenue"),
                ebitda_margin=record.get("ebitda_margin"),
                burn_multiple=record.get("burn_multiple"),
                source_system=record["source_system"],
                crm_updated_at=datetime.fromisoformat(record["updated_at"]),
                last_sync_run_id=sync_run_id,
            )
        )
        return "inserted"

    def _load_update(self, record: dict[str, Any], sync_run_id: int) -> str:
        existing = self.db.scalar(select(ReportingUpdate).where(ReportingUpdate.external_id == record["external_id"]))
        if existing:
            existing.company_external_id = record["company_external_id"]
            existing.reporting_period = record["reporting_period"]
            existing.update_type = record["update_type"]
            existing.summary = record["summary"]
            existing.source_system = record["source_system"]
            existing.crm_updated_at = datetime.fromisoformat(record["updated_at"])
            existing.last_sync_run_id = sync_run_id
            return "updated"
        self.db.add(
            ReportingUpdate(
                external_id=record["external_id"],
                company_external_id=record["company_external_id"],
                reporting_period=record["reporting_period"],
                update_type=record["update_type"],
                summary=record["summary"],
                source_system=record["source_system"],
                crm_updated_at=datetime.fromisoformat(record["updated_at"]),
                last_sync_run_id=sync_run_id,
            )
        )
        return "inserted"
