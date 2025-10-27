"""
Command-line entry point for the QTickets API ingestion pipeline.

This loader replaces the legacy Google Sheets flow by pulling sales and
inventory data directly from the official API and writing the results into
ClickHouse staging tables and facts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Sequence

from dotenv import load_dotenv

# Ensure the project root is in PYTHONPATH for direct invocation.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from integrations.common import (  # noqa: E402  pylint: disable=wrong-import-position
    ClickHouseClient,
    get_client,
    now_msk,
    setup_integrations_logger,
    to_msk,
)

from .client import QticketsApiClient, QticketsApiError  # noqa: E402
from .config import ConfigError, QticketsApiConfig  # noqa: E402
from .inventory_agg import build_inventory_snapshot  # noqa: E402
from .transform import transform_orders_to_sales_rows  # noqa: E402


logger = setup_integrations_logger("qtickets_api")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI argument parsing."""
    parser = argparse.ArgumentParser(description="QTickets API → ClickHouse loader")
    parser.add_argument(
        "--envfile",
        required=True,
        help="Path to the dotenv file containing QTickets API credentials",
    )
    parser.add_argument(
        "--ch-env",
        help="Optional dotenv file with ClickHouse overrides (fallback to envfile values)",
    )
    parser.add_argument(
        "--since-hours",
        type=int,
        default=24,
        help="Lookback window in hours for orders (default: 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and transform data without writing to ClickHouse",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (LOG_LEVEL=DEBUG)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"

    started_at = now_msk()
    job_name = "qtickets_api"
    run_version = int(time.time())

    try:
        config = QticketsApiConfig.load(args.envfile)
        if args.ch_env:
            load_dotenv(args.ch_env, override=True)

        ch_client = get_client(args.ch_env)
        client = QticketsApiClient(base_url=config.base_url, token=config.token, logger=logger)

        window_end = now_msk()
        window_start = window_end - timedelta(hours=max(args.since_hours, 1))

        logger.info(
            "Starting QTickets API ingestion run",
            metrics={
                "job": job_name,
                "since_hours": args.since_hours,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "_ver": run_version,
            },
        )

        events = client.list_events()
        orders = client.list_orders(window_start, window_end)

        try:
            inventory_rows = build_inventory_snapshot(events, client, snapshot_ts=window_end)
        except NotImplementedError as exc:
            logger.warning(
                "Inventory snapshot skipped: show_id resolution not implemented",
                metrics={"reason": str(exc)},
            )
            inventory_rows = []

        sales_rows = transform_orders_to_sales_rows(orders, version=run_version)
        inventory_stage_rows = _augment_inventory_rows(inventory_rows, run_version)
        events_rows = _transform_events(events, run_version)
        sales_daily_rows = _aggregate_sales_daily(sales_rows, run_version)

        metrics = {
            "events": len(events),
            "orders": len(orders),
            "sales_rows": len(sales_rows),
            "inventory_rows": len(inventory_stage_rows),
            "sales_daily_rows": len(sales_daily_rows),
        }

        if args.dry_run:
            logger.info("Dry-run complete, no data written to ClickHouse", metrics=metrics)
            return

        _load_clickhouse(
            ch_client=ch_client,
            sales_stage_rows=sales_rows,
            inventory_stage_rows=inventory_stage_rows,
            events_rows=events_rows,
            sales_daily_rows=sales_daily_rows,
        )

        _record_job_run(
            ch_client=ch_client,
            job=job_name,
            status="ok",
            started_at=started_at,
            finished_at=now_msk(),
            metrics=metrics,
        )

        logger.info("QTickets API ingestion completed successfully", metrics=metrics)

    except (ConfigError, QticketsApiError) as exc:
        logger.error("Configuration or API error", metrics={"error": str(exc)})
        _safe_record_failure(job_name, started_at, str(exc), dry_run=args.dry_run)
        raise SystemExit(1)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected failure during QTickets API ingestion", metrics={"error": str(exc)})
        _safe_record_failure(job_name, started_at, str(exc), dry_run=args.dry_run)
        raise SystemExit(1)


# --------------------------------------------------------------------- #
# ClickHouse loaders
# --------------------------------------------------------------------- #
def _load_clickhouse(
    *,
    ch_client: ClickHouseClient,
    sales_stage_rows: Sequence[Dict[str, Any]],
    inventory_stage_rows: Sequence[Dict[str, Any]],
    events_rows: Sequence[Dict[str, Any]],
    sales_daily_rows: Sequence[Dict[str, Any]],
) -> None:
    """Persist staging and fact tables to ClickHouse."""
    if sales_stage_rows:
        ch_client.insert("zakaz.stg_qtickets_api_orders_raw", list(sales_stage_rows))

    if inventory_stage_rows:
        ch_client.insert("zakaz.stg_qtickets_api_inventory_raw", list(inventory_stage_rows))

    if events_rows:
        ch_client.insert("zakaz.dim_events", list(events_rows))

    if sales_daily_rows:
        ch_client.insert("zakaz.fact_qtickets_sales_daily", list(sales_daily_rows))

    if inventory_stage_rows:
        # Use the same rows with _ver to update the latest snapshot fact table.
        latest_rows = [
            {
                "snapshot_ts": row["snapshot_ts"],
                "event_id": row["event_id"],
                "event_name": row["event_name"],
                "city": row["city"],
                "tickets_total": row["tickets_total"],
                "tickets_left": row["tickets_left"],
                "_ver": row["_ver"],
            }
            for row in inventory_stage_rows
        ]
        ch_client.insert("zakaz.fact_qtickets_inventory_latest", latest_rows)


def _record_job_run(
    *,
    ch_client: ClickHouseClient,
    job: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    metrics: Dict[str, Any],
) -> None:
    """Persist a meta_job_runs entry."""
    payload = {
        "job": job,
        "started_at": started_at.replace(tzinfo=None),
        "finished_at": finished_at.replace(tzinfo=None),
        "rows_processed": int(metrics.get("sales_rows", 0) + metrics.get("inventory_rows", 0)),
        "status": status,
        "message": json.dumps(
            {
                "orders": metrics.get("orders", 0),
                "events": metrics.get("events", 0),
            },
            ensure_ascii=False,
        ),
        "metrics": json.dumps(metrics, ensure_ascii=False),
    }
    ch_client.insert("zakaz.meta_job_runs", [payload])


def _safe_record_failure(job: str, started_at: datetime, message: str, *, dry_run: bool) -> None:
    """
    Record job failure in ClickHouse when possible without raising secondary errors.

    The function loads configuration defaults to honour the same envfile used for
    the main execution.  It never raises to keep the original exception visible.
    """
    if dry_run:
        logger.warning(
            "Skipping failure recording because the loader was invoked with --dry-run",
            metrics={"job": job, "error": message},
        )
        return

    try:
        ch_client = get_client()
        _record_job_run(
            ch_client=ch_client,
            job=job,
            status="failed",
            started_at=started_at,
            finished_at=now_msk(),
            metrics={"error": message},
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Unable to record failure in meta_job_runs",
            metrics={"job": job, "error": message, "secondary_error": str(exc)},
        )


# --------------------------------------------------------------------- #
# Transform helpers
# --------------------------------------------------------------------- #
def _augment_inventory_rows(rows: Sequence[Dict[str, Any]], version: int) -> List[Dict[str, Any]]:
    """Attach metadata required by ClickHouse staging tables."""
    import hashlib  # Local import to avoid polluting module namespace.

    augmented: List[Dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        record["_ver"] = int(version)
        key_src = f"{record.get('event_id', '')}::{record.get('snapshot_ts', '')}"
        record["_dedup_key"] = hashlib.md5(key_src.encode("utf-8")).hexdigest()
        augmented.append(record)
    return augmented


def _transform_events(events: Sequence[Dict[str, Any]], version: int) -> List[Dict[str, Any]]:
    """Prepare event dimension rows."""
    rows: List[Dict[str, Any]] = []
    for event in events:
        event_id = event.get("id") or event.get("event_id")
        if not event_id:
            continue

        start_date = _coerce_date(
            event.get("start_date")
            or event.get("start_at")
            or event.get("begin_date")
            or event.get("start_time")
        )
        end_date = _coerce_date(
            event.get("finish_date")
            or event.get("end_date")
            or event.get("finish_at")
            or event.get("end_time")
        )

        rows.append(
            {
                "event_id": str(event_id),
                "event_name": (event.get("name") or event.get("event_name") or "").strip(),
                "city": (event.get("city") or "").strip().lower(),
                "start_date": start_date,
                "end_date": end_date,
                "_ver": int(version),
            }
        )

    return rows


def _coerce_date(value: Any) -> date | None:
    """Convert various field shapes into a ``date`` or ``None``."""
    if not value:
        return None

    try:
        dt = to_msk(value)
        return dt.date()
    except Exception:
        return None


def _aggregate_sales_daily(rows: Sequence[Dict[str, Any]], version: int) -> List[Dict[str, Any]]:
    """Roll raw sales rows by day/event/city."""
    buckets: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"tickets_sold": 0, "revenue": 0.0})

    for row in rows:
        sale_ts = row.get("sale_ts")
        if not isinstance(sale_ts, datetime):
            continue

        key = (row.get("event_id"), row.get("city"), sale_ts.date())
        bucket = buckets[key]
        bucket["tickets_sold"] += int(row.get("tickets_sold", 0))
        bucket["revenue"] += float(row.get("revenue", 0))

    aggregated: List[Dict[str, Any]] = []
    for (event_id, city, sales_date), values in buckets.items():
        aggregated.append(
            {
                "sales_date": sales_date,
                "event_id": event_id,
                "city": city,
                "tickets_sold": int(values["tickets_sold"]),
                "revenue": float(values["revenue"]),
                "_ver": int(version),
            }
        )

    return aggregated


if __name__ == "__main__":
    main()
