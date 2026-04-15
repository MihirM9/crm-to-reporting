"""
MCP server for the CRM-to-Reporting pipeline.

Implements a minimal Model Context Protocol stdio server (JSON-RPC 2.0 over
newline-delimited stdin/stdout). No external MCP SDK required.

Why hand-rolled: the MCP wire protocol is small, and implementing it directly
keeps the project dependency-light and shows explicit understanding of how
Claude Code talks to external tools.

Run manually:
    python -m mcp_server.server

Claude Code config (~/.claude/mcp.json or project .mcp.json):
    {
      "mcpServers": {
        "crm-reporting": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/absolute/path/to/this/project"
        }
      }
    }
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func, select

from db.init_db import init_db
from db.models import (
    DealPipeline,
    GeneratedReport,
    RejectedRecord,
    ReportingCompany,
    ReportingMetric,
    ReportingUpdate,
    SyncRun,
)
from db.session import SessionLocal
from services.sync_service import SyncService


# Log to stderr only — stdout is reserved for JSON-RPC frames.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="[mcp-server] %(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "crm-reporting"
SERVER_VERSION = "0.1.0"


# ----------------------------------------------------------------------------
# Tool implementations — each returns a plain dict that will be JSON-serialized.
# Framed in private-credit vocabulary: companies=borrowers, deals=facilities,
# metrics=covenant KPIs.
# ----------------------------------------------------------------------------

def _serialize_row(row: Any) -> dict:
    """Serialize a SQLAlchemy row to a JSON-safe dict."""
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        payload[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return payload


def tool_run_sync(args: dict) -> dict:
    """Trigger a fresh sync run from CRM source → reporting layer."""
    trigger_mode = args.get("trigger_mode", "mcp")
    db = SessionLocal()
    try:
        sync_run = SyncService(db).run_sync(trigger_mode=trigger_mode)
        return {
            "sync_run_id": sync_run.id,
            "status": sync_run.status,
            "extracted": sync_run.extracted_count,
            "inserted": sync_run.loaded_inserted_count,
            "updated": sync_run.loaded_updated_count,
            "rejected": sync_run.rejected_count,
            "duration_ms": sync_run.duration_ms,
            "status_message": sync_run.status_message,
            "warnings": sync_run.warnings or [],
        }
    finally:
        db.close()


def tool_get_latest_sync(args: dict) -> dict:
    """Return the most recent sync run with full metrics."""
    db = SessionLocal()
    try:
        run = db.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()))
        if not run:
            return {"message": "No sync runs recorded yet."}
        return _serialize_row(run)
    finally:
        db.close()


def tool_list_sync_runs(args: dict) -> dict:
    """List recent sync runs for audit trail review."""
    limit = min(int(args.get("limit", 10)), 100)
    db = SessionLocal()
    try:
        runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)).all()
        return {"count": len(runs), "runs": [_serialize_row(r) for r in runs]}
    finally:
        db.close()


def tool_list_borrowers(args: dict) -> dict:
    """List borrowers (portfolio companies) in the reporting layer.

    Optional filters: stage, owner, reporting_period.
    """
    db = SessionLocal()
    try:
        query = select(ReportingCompany)
        if stage := args.get("stage"):
            query = query.where(ReportingCompany.stage == stage)
        if owner := args.get("owner"):
            query = query.where(ReportingCompany.owner == owner)
        if period := args.get("reporting_period"):
            query = query.where(ReportingCompany.reporting_period == period)
        rows = db.scalars(query.order_by(ReportingCompany.company_name)).all()
        return {"count": len(rows), "borrowers": [_serialize_row(r) for r in rows]}
    finally:
        db.close()


def tool_list_facilities(args: dict) -> dict:
    """List facilities / deals in the pipeline, optionally filtered by stage."""
    db = SessionLocal()
    try:
        query = select(DealPipeline)
        if stage := args.get("stage"):
            query = query.where(DealPipeline.stage == stage)
        if owner := args.get("owner"):
            query = query.where(DealPipeline.owner == owner)
        rows = db.scalars(query.order_by(DealPipeline.crm_updated_at.desc())).all()
        return {"count": len(rows), "facilities": [_serialize_row(r) for r in rows]}
    finally:
        db.close()


def tool_get_kpi_movements(args: dict) -> dict:
    """Return period-over-period revenue movements for each borrower.

    This is the core 'what moved this quarter?' question a PM would ask
    before drafting an LP letter.
    """
    db = SessionLocal()
    try:
        metrics = db.scalars(
            select(ReportingMetric).order_by(
                ReportingMetric.company_external_id, ReportingMetric.reporting_period
            )
        ).all()
        latest: dict[str, ReportingMetric] = {}
        prior: dict[str, ReportingMetric] = {}
        for m in metrics:
            cur = latest.get(m.company_external_id)
            if cur is None or m.reporting_period > cur.reporting_period:
                if cur is not None:
                    prior[m.company_external_id] = cur
                latest[m.company_external_id] = m

        movements = []
        for company_id, lm in latest.items():
            pm = prior.get(company_id)
            entry = {
                "company_external_id": company_id,
                "latest_period": lm.reporting_period,
                "latest_revenue": lm.revenue,
                "latest_ebitda_margin": lm.ebitda_margin,
                "latest_burn_multiple": lm.burn_multiple,
                "prior_period": pm.reporting_period if pm else None,
                "prior_revenue": pm.revenue if pm else None,
            }
            if pm and lm.revenue is not None and pm.revenue is not None:
                entry["revenue_delta"] = lm.revenue - pm.revenue
                entry["revenue_delta_pct"] = (
                    round((lm.revenue - pm.revenue) / pm.revenue * 100, 2) if pm.revenue else None
                )
            movements.append(entry)
        return {"count": len(movements), "movements": movements}
    finally:
        db.close()


def tool_list_watchlist(args: dict) -> dict:
    """Identify borrowers on a credit watch list based on covenant KPIs.

    A borrower goes on the watch list if any of these are true for the
    latest reporting period:
      - EBITDA margin is negative
      - Burn multiple > 2.0  (cash consumption > 2x net new ARR)
      - Revenue declined period-over-period
      - Latest metrics missing entirely for a portfolio company
    """
    db = SessionLocal()
    try:
        movements = tool_get_kpi_movements({})["movements"]
        companies = {
            c.external_id: c
            for c in db.scalars(
                select(ReportingCompany).where(ReportingCompany.stage == "portfolio")
            ).all()
        }
        watchlist = []
        for m in movements:
            reasons = []
            if m.get("latest_ebitda_margin") is not None and m["latest_ebitda_margin"] < 0:
                reasons.append(f"negative EBITDA margin ({m['latest_ebitda_margin']:.1%})")
            if m.get("latest_burn_multiple") is not None and m["latest_burn_multiple"] > 2.0:
                reasons.append(f"burn multiple {m['latest_burn_multiple']} exceeds 2.0x threshold")
            if m.get("revenue_delta") is not None and m["revenue_delta"] < 0:
                reasons.append(f"revenue declined {m['revenue_delta']:,.0f} QoQ")
            if reasons:
                company = companies.get(m["company_external_id"])
                watchlist.append(
                    {
                        "company_external_id": m["company_external_id"],
                        "company_name": company.company_name if company else None,
                        "owner": company.owner if company else None,
                        "latest_period": m["latest_period"],
                        "reasons": reasons,
                    }
                )
        return {"count": len(watchlist), "watchlist": watchlist}
    finally:
        db.close()


def tool_list_rejected_records(args: dict) -> dict:
    """List records that failed validation and are in quarantine."""
    limit = min(int(args.get("limit", 25)), 200)
    db = SessionLocal()
    try:
        query = select(RejectedRecord).order_by(RejectedRecord.created_at.desc()).limit(limit)
        if entity := args.get("entity_type"):
            query = select(RejectedRecord).where(RejectedRecord.entity_type == entity).order_by(
                RejectedRecord.created_at.desc()
            ).limit(limit)
        rows = db.scalars(query).all()
        return {"count": len(rows), "rejected": [_serialize_row(r) for r in rows]}
    finally:
        db.close()


def tool_list_reports(args: dict) -> dict:
    """List generated investor/internal reports."""
    db = SessionLocal()
    try:
        query = select(GeneratedReport).order_by(GeneratedReport.created_at.desc())
        if report_type := args.get("report_type"):
            query = query.where(GeneratedReport.report_type == report_type)
        rows = db.scalars(query).all()
        return {"count": len(rows), "reports": [_serialize_row(r) for r in rows]}
    finally:
        db.close()


def tool_read_report(args: dict) -> dict:
    """Read the full text contents of a generated report by ID."""
    report_id = args.get("report_id")
    if report_id is None:
        raise ValueError("report_id is required")
    db = SessionLocal()
    try:
        report = db.scalar(select(GeneratedReport).where(GeneratedReport.id == int(report_id)))
        if not report:
            return {"error": f"Report {report_id} not found"}
        path = Path(report.file_path)
        if not path.exists():
            return {"error": f"Report file missing on disk: {path}"}
        return {
            "report_id": report.id,
            "report_type": report.report_type,
            "output_format": report.output_format,
            "sync_run_id": report.sync_run_id,
            "content": path.read_text(encoding="utf-8"),
        }
    finally:
        db.close()


def tool_get_pipeline_stats(args: dict) -> dict:
    """Return counts across CRM, reporting layer, and rejects — the dashboard at a glance."""
    db = SessionLocal()
    try:
        return {
            "reporting_borrowers": db.scalar(select(func.count()).select_from(ReportingCompany)) or 0,
            "reporting_facilities": db.scalar(select(func.count()).select_from(DealPipeline)) or 0,
            "reporting_metrics": db.scalar(select(func.count()).select_from(ReportingMetric)) or 0,
            "reporting_updates": db.scalar(select(func.count()).select_from(ReportingUpdate)) or 0,
            "total_sync_runs": db.scalar(select(func.count()).select_from(SyncRun)) or 0,
            "successful_sync_runs": db.scalar(
                select(func.count()).select_from(SyncRun).where(SyncRun.status == "success")
            ) or 0,
            "failed_sync_runs": db.scalar(
                select(func.count()).select_from(SyncRun).where(SyncRun.status == "failed")
            ) or 0,
            "total_rejected_records": db.scalar(select(func.count()).select_from(RejectedRecord)) or 0,
            "total_generated_reports": db.scalar(select(func.count()).select_from(GeneratedReport)) or 0,
        }
    finally:
        db.close()


# ----------------------------------------------------------------------------
# Tool registry — shape matches MCP tools/list response.
# ----------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "run_sync",
        "description": "Trigger a fresh ETL sync run from the CRM source into the reporting layer. Returns run metrics (extracted, inserted, updated, rejected). Use this when new borrower data may have landed and the reporting layer needs to be refreshed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger_mode": {
                    "type": "string",
                    "description": "Label for how this run was triggered (default: 'mcp').",
                }
            },
        },
        "handler": tool_run_sync,
    },
    {
        "name": "get_latest_sync",
        "description": "Get the most recent sync run with full metrics, status, and any batch warnings. First stop for 'did our last sync succeed?'",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_get_latest_sync,
    },
    {
        "name": "list_sync_runs",
        "description": "List recent sync runs for audit trail review. Useful when LPs or auditors ask to see pipeline execution history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max runs to return (default 10, max 100)."}
            },
        },
        "handler": tool_list_sync_runs,
    },
    {
        "name": "list_borrowers",
        "description": "List borrowers (portfolio companies) from the cleaned reporting layer. Optionally filter by stage (new, qualified, portfolio, monitoring, realized), owner, or reporting period.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string"},
                "owner": {"type": "string"},
                "reporting_period": {"type": "string"},
            },
        },
        "handler": tool_list_borrowers,
    },
    {
        "name": "list_facilities",
        "description": "List credit facilities / deals currently in pipeline. Optionally filter by stage (sourced, screening, ic, term_sheet, closed_won, closed_lost) or deal owner.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string"},
                "owner": {"type": "string"},
            },
        },
        "handler": tool_list_facilities,
    },
    {
        "name": "get_kpi_movements",
        "description": "Return period-over-period revenue, EBITDA margin, and burn multiple movements for each borrower. This is the 'what moved this quarter?' query that drives LP letter highlights.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_get_kpi_movements,
    },
    {
        "name": "list_watchlist",
        "description": "Identify borrowers on a credit watchlist — negative EBITDA margin, burn multiple > 2.0x, or declining revenue. This is what a portfolio manager would ask for before a weekly credit review meeting.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_list_watchlist,
    },
    {
        "name": "list_rejected_records",
        "description": "List records that failed validation and are in quarantine (missing required fields, bad types, invalid stage values). Use when reconciling why a borrower is missing from the reporting layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "entity_type": {"type": "string", "description": "Filter: companies, deals, metrics, updates."},
            },
        },
        "handler": tool_list_rejected_records,
    },
    {
        "name": "list_reports",
        "description": "List generated investor and internal update reports with sync run lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "description": "Filter: investor or internal."}
            },
        },
        "handler": tool_list_reports,
    },
    {
        "name": "read_report",
        "description": "Return the full text content of a generated report by ID. Use this to pull an auto-drafted LP letter directly into a conversation for editing.",
        "inputSchema": {
            "type": "object",
            "properties": {"report_id": {"type": "integer"}},
            "required": ["report_id"],
        },
        "handler": tool_read_report,
    },
    {
        "name": "get_pipeline_stats",
        "description": "One-shot view of counts across reporting layer, sync runs, and quarantine. Quick 'is the pipeline healthy?' check.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_get_pipeline_stats,
    },
]


# Build handler lookup once
HANDLERS: dict[str, Callable[[dict], dict]] = {t["name"]: t["handler"] for t in TOOLS}


# ----------------------------------------------------------------------------
# MCP protocol: newline-delimited JSON-RPC 2.0 over stdin/stdout.
# ----------------------------------------------------------------------------

def _write_frame(payload: dict) -> None:
    """Write a JSON-RPC frame to stdout and flush."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _error_response(request_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _success_response(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_request(request: dict) -> dict | None:
    """Route a single JSON-RPC request to the appropriate handler."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    # Notifications (no id) — we log and skip.
    if request_id is None:
        logger.info("Notification received: %s", method)
        return None

    if method == "initialize":
        return _success_response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "tools/list":
        public_tools = [
            {k: v for k, v in tool.items() if k != "handler"} for tool in TOOLS
        ]
        return _success_response(request_id, {"tools": public_tools})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return _error_response(request_id, -32601, f"Unknown tool: {name}")
        try:
            result = handler(arguments)
            return _success_response(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(result, indent=2, default=str)}
                    ]
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface any tool error as MCP error
            logger.exception("Tool %s failed", name)
            return _error_response(
                request_id,
                -32603,
                f"Tool '{name}' failed: {exc}\n{traceback.format_exc()}",
            )

    if method == "ping":
        return _success_response(request_id, {})

    return _error_response(request_id, -32601, f"Method not found: {method}")


def run() -> None:
    """Run the MCP stdio loop until stdin closes."""
    init_db()  # ensure schema exists before any tool runs
    logger.info("MCP server ready — %d tools registered", len(TOOLS))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.error("Bad JSON frame: %s", exc)
            _write_frame(_error_response(None, -32700, f"Parse error: {exc}"))
            continue

        response = handle_request(request)
        if response is not None:
            _write_frame(response)


if __name__ == "__main__":
    run()
