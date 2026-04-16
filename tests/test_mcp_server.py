"""Integration test for the MCP stdio server.

Drives the server via its handle_request() entry point, which is how a
real MCP client (Claude Code) would talk to it — just without the
JSON-RPC framing. This lets us verify the protocol surface and every
tool handler without spawning a subprocess.
"""
from __future__ import annotations

import json

import pytest

from db.init_db import init_db
from db.seed_data import seed_mock_crm
from db.session import SessionLocal
from main import app
from mcp_server.server import TOOLS, handle_request
from services.crm_client import CRMClient


def _seed():
    init_db()
    db = SessionLocal()
    try:
        seed_mock_crm(db)
    finally:
        db.close()


@pytest.fixture
def patched_crm(monkeypatch):
    """Route CRMClient calls through the Flask test client instead of real HTTP."""
    test_client = app.test_client()

    def fake_fetch_incremental(self, entity: str, updated_since):
        response = test_client.get(
            f"/api/mock-crm/{entity}", query_string={"limit": 50, "offset": 0}
        )
        assert response.status_code == 200
        return response.get_json()["data"]

    monkeypatch.setattr(CRMClient, "fetch_incremental", fake_fetch_incremental)
    return test_client


def _extract_text(response: dict) -> dict:
    """Pull the JSON payload out of a tools/call response."""
    assert "result" in response, response
    content = response["result"]["content"]
    assert content and content[0]["type"] == "text"
    return json.loads(content[0]["text"])


def test_mcp_initialize():
    resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "crm-reporting"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_tools_list():
    resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    # All tools registered in TOOLS must appear in the list
    assert tool_names == {t["name"] for t in TOOLS}
    # Handlers must not leak into the public listing
    assert all("handler" not in t for t in tools)
    # Every tool must have a description and inputSchema
    for tool in tools:
        assert tool.get("description")
        assert tool.get("inputSchema", {}).get("type") == "object"


def test_mcp_run_sync_and_downstream_tools(patched_crm):
    _seed()

    # 1. Trigger a sync
    resp = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "run_sync", "arguments": {"trigger_mode": "test"}},
        }
    )
    sync_result = _extract_text(resp)
    assert sync_result["status"] == "success"
    assert sync_result["extracted"] >= 1
    assert sync_result["rejected"] >= 1  # seed data intentionally contains bad rows

    # 2. Latest sync should reflect what we just ran
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_latest_sync", "arguments": {}}}
    )
    assert _extract_text(resp)["status"] == "success"

    # 3. Borrowers should include Northstar Health
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "list_borrowers", "arguments": {}}}
    )
    borrowers = _extract_text(resp)["borrowers"]
    names = {b["company_name"] for b in borrowers}
    assert "Northstar Health" in names

    # 4. KPI movements should include at least one period-over-period delta
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "get_kpi_movements", "arguments": {}}}
    )
    movements = _extract_text(resp)["movements"]
    assert any(m.get("revenue_delta") is not None for m in movements)

    # 5. Watchlist should flag Pinnacle (negative EBITDA, burn > 2x)
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "list_watchlist", "arguments": {}}}
    )
    watchlist = _extract_text(resp)["watchlist"]
    flagged = {w["company_external_id"] for w in watchlist}
    assert "COMP-107" in flagged  # Pinnacle Fintech has negative EBITDA

    # 6. Rejected records should be populated
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "list_rejected_records", "arguments": {"limit": 10}}}
    )
    assert _extract_text(resp)["count"] >= 1

    # 7. Reports list and read
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "list_reports", "arguments": {}}}
    )
    reports = _extract_text(resp)["reports"]
    assert len(reports) >= 2
    first_md = next(r for r in reports if r["output_format"] == "markdown")
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
         "params": {"name": "read_report", "arguments": {"report_id": first_md["id"]}}}
    )
    assert "Portfolio" in _extract_text(resp)["content"] or "Sync" in _extract_text(resp)["content"]

    # 8. Reconciliation breaks — CRM vs fund admin should produce breaks
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
         "params": {"name": "list_reconciliation_breaks", "arguments": {}}}
    )
    recon = _extract_text(resp)
    assert recon["count"] >= 1  # seed data has valuation + stage discrepancies
    # Verdant Energy should have a material valuation break ($210M vs $195M)
    verdant_breaks = [b for b in recon["breaks"] if b["borrower_external_id"] == "COMP-106"]
    assert any(b["field"] == "valuation" for b in verdant_breaks)

    # 9. Covenant breaches — Pinnacle should breach min_ebitda_margin (negative)
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 12, "method": "tools/call",
         "params": {"name": "list_covenant_breaches", "arguments": {}}}
    )
    breaches = _extract_text(resp)
    assert breaches["count"] >= 1
    pinnacle_breaches = [b for b in breaches["breaches"] if b["borrower_external_id"] == "COMP-107"]
    assert len(pinnacle_breaches) >= 1  # negative EBITDA margin and/or burn > 2.5

    # 10. Pipeline stats should include new counters
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 13, "method": "tools/call",
         "params": {"name": "get_pipeline_stats", "arguments": {}}}
    )
    stats = _extract_text(resp)
    assert stats["total_reconciliation_breaks"] >= 1
    assert stats["total_covenant_breaches"] >= 1


def test_mcp_unknown_tool_returns_error():
    resp = handle_request(
        {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
         "params": {"name": "nonexistent_tool", "arguments": {}}}
    )
    assert "error" in resp
    assert "Unknown tool" in resp["error"]["message"]
