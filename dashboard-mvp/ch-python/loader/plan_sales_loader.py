"""
Simple CLI loader for plan sales table.

Usage:
    python -m ch-python.loader.plan_sales_loader --csv path/to/plan.csv [--envfile secrets/.env.clickhouse]

CSV columns (header required):
    sales_date (YYYY-MM-DD), event_id, city, plan_tickets, plan_revenue
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime, date
from typing import Any, Dict, List

from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from integrations.common import ClickHouseClient  # noqa: E402


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value.strip()).date()


def _parse_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _parse_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def load_csv(path: str, version: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for line in reader:
            sales_date_raw = (line.get("sales_date") or "").strip()
            if not sales_date_raw:
                continue
            rows.append(
                {
                    "sales_date": _parse_date(sales_date_raw),
                    "event_id": (line.get("event_id") or "").strip(),
                    "city": (line.get("city") or "").strip().lower(),
                    "plan_tickets": _parse_int(line.get("plan_tickets") or 0),
                    "plan_revenue": _parse_float(line.get("plan_revenue") or 0.0),
                    "_ver": version,
                }
            )
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load plan sales CSV into ClickHouse")
    parser.add_argument("--csv", required=True, help="Path to CSV with plan rows")
    parser.add_argument(
        "--envfile",
        help="Optional dotenv file with ClickHouse connection variables",
    )
    args = parser.parse_args(argv)

    if args.envfile:
        load_dotenv(args.envfile, override=True)

    version = int(time.time())
    rows = load_csv(args.csv, version)
    if not rows:
        print("No rows parsed from CSV, nothing to load")
        return

    db = os.getenv("CH_DATABASE") or "zakaz"
    client = ClickHouseClient()
    client.insert(f"{db}.plan_sales", rows)
    print(f"Loaded {len(rows)} plan rows into {db}.plan_sales (version={version})")


if __name__ == "__main__":
    main()
