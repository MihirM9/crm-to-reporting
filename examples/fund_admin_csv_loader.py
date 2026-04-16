"""Example loader for a real-ish fund admin CSV extract.

This is a reference file, not a production ingest job. It shows the minimum
shape needed to transform an admin-delivered CSV into the reporting/recon
records used by this demo.
"""
from __future__ import annotations

import csv
from pathlib import Path


def load_fund_admin_positions(csv_path: str) -> list[dict]:
    rows: list[dict] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "external_id": row["position_id"],
                    "borrower_external_id": row["borrower_id"],
                    "borrower_name": row["borrower_name"],
                    "reporting_period": row["reporting_period"],
                    "fund_admin_valuation": float(row["fair_value"]) if row.get("fair_value") else None,
                    "fund_admin_principal_balance": float(row["principal_balance"]) if row.get("principal_balance") else None,
                    "fund_admin_stage": row.get("credit_stage"),
                    "source_system": "fund_admin_csv",
                }
            )
    return rows


if __name__ == "__main__":
    sample = load_fund_admin_positions("sample_positions.csv")
    print(f"Loaded {len(sample)} fund admin positions from CSV example.")
