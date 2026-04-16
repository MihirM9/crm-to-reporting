"""Real-ish CRM adapter example for swapping the demo source with a live API.

This file is intentionally not imported by the app. It is a reference for how
to replace the mock CRM source without rewriting the rest of the pipeline.

Example assumptions:
- The external CRM supports bearer-token auth.
- Records can be filtered with an `updated_since` style parameter.
- The vendor response is paginated.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests


class RealCRMAdapter:
    def __init__(self) -> None:
        self.base_url = os.environ["REAL_CRM_BASE_URL"].rstrip("/")
        self.api_token = os.environ["REAL_CRM_API_TOKEN"]
        self.timeout = int(os.getenv("REAL_CRM_TIMEOUT_SECONDS", "10"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def fetch_companies(self, updated_since: datetime | None = None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {"limit": 100}
            if updated_since:
                params["updated_since"] = updated_since.isoformat()
            if cursor:
                params["cursor"] = cursor

            response = requests.get(
                f"{self.base_url}/companies",
                headers=self._headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()

            for row in payload["data"]:
                records.append(
                    {
                        "external_id": row["id"],
                        "name": row.get("company_name"),
                        "owner": row.get("relationship_owner"),
                        "stage": row.get("lifecycle_stage"),
                        "reporting_period": row.get("reporting_period"),
                        "valuation": row.get("enterprise_value"),
                        "updated_at": row["updated_at"],
                        "source_system": "live_crm",
                    }
                )

            cursor = payload.get("next_cursor")
            if not cursor:
                break

        return records


if __name__ == "__main__":
    adapter = RealCRMAdapter()
    companies = adapter.fetch_companies()
    print(f"Fetched {len(companies)} companies from live CRM example adapter.")
