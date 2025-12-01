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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

# Ensure the project root is in PYTHONPATH for direct invocation.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from integrations.common import (  # noqa: E402  pylint: disable=wrong-import-position
    ClickHouseClient,
    get_client,
    get_client_from_config,
    now_msk,
    setup_integrations_logger,
    to_msk,
)

from .client import QticketsApiClient, QticketsApiError  # noqa: E402
from .config import ConfigError, QticketsApiConfig  # noqa: E402
from .inventory_agg import build_inventory_snapshot  # noqa: E402
from .transform import (
    transform_barcodes,
    transform_clients,
    transform_discounts,
    transform_orders_to_sales_rows,
    transform_partner_tickets,
    transform_price_shades,
    transform_promo_codes,
)  # noqa: E402


logger = setup_integrations_logger("qtickets_api")
NON_FATAL_HTTP_STATUSES = {403, 404}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI argument parsing."""
    parser = argparse.ArgumentParser(description="QTickets API to ClickHouse loader")
    parser.add_argument(
        "--envfile",
        required=False,
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
        "--offline-fixtures-dir",
        help="Use fixtures from this directory instead of making real API calls",
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
    run_version = int(time.time())
    # Defaults in case configuration loading fails early
    job_name = os.getenv("JOB_NAME", "qtickets_api")
    dry_run = bool(args.dry_run)
    since_hours = args.since_hours
    backfill_mode = False
    ch_client: ClickHouseClient | None = None
    skipped_resources: List[Dict[str, Any]] = []

    try:
        # Load dotenv files (QTickets env first, then optional ClickHouse overrides)
        if args.envfile:
            load_dotenv(args.envfile, override=True)
        if args.ch_env:
            load_dotenv(args.ch_env, override=True)

        # Build runtime configuration from the merged environment.
        config = QticketsApiConfig.load()

        # Override with command line arguments if provided
        since_hours = (
            args.since_hours if args.since_hours != 24 else config.qtickets_since_hours
        )
        dry_run = bool(args.dry_run or config.dry_run)
        job_name = config.job_name

        # Skip ClickHouse client in dry-run mode
        ch_client = None if dry_run else get_client_from_config(config)

        database_prefix = (
            "zakaz_test" if os.getenv("CH_DATABASE") == "zakaz_test" else config.clickhouse_db
        )

        if (
            not dry_run
            and ch_client is not None
            and config.initial_backfill_hours
        ):
            try:
                guard_table = f"{database_prefix}.{config.backfill_guard_table}"
                result = ch_client.execute(
                    f"SELECT count() FROM {guard_table} WHERE job = %(job)s",
                    {"job": job_name},
                )
                existing_runs = 0
                if hasattr(result, "first_item"):
                    try:
                        existing_runs = int(result.first_item)  # type: ignore[arg-type]
                    except Exception:  # pylint: disable=broad-except
                        existing_runs = 0
                elif getattr(result, "result_rows", None):
                    existing_runs = int(result.result_rows[0][0])
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Unable to determine if initial backfill is needed; proceeding with default window",
                    metrics={"job": job_name, "error": str(exc)},
                )
            else:
                if existing_runs == 0:
                    backfill_mode = True
                    since_hours = max(since_hours, config.initial_backfill_hours)
                    logger.info(
                        "Initial backfill enabled (no previous runs found)",
                        metrics={
                            "job": job_name,
                            "since_hours": since_hours,
                            "initial_backfill_hours": config.initial_backfill_hours,
                            "_ver": run_version,
                        },
                    )
                else:
                    logger.debug(
                        "Previous runs detected; using incremental window",
                        metrics={
                            "job": job_name,
                            "since_hours": since_hours,
                            "initial_backfill_hours": config.initial_backfill_hours,
                            "existing_runs": existing_runs,
                        },
                    )

        # Use fixtures if in offline mode
        if args.offline_fixtures_dir:
            events, orders = _load_fixtures(args.offline_fixtures_dir)
            client = None  # No real client needed in offline mode
            clients_payload = []
            price_shades_payload = []
            discounts_payload = []
            promo_codes_payload = []
            barcodes_payload = []
            partner_tickets_payload = []
        else:
            client = QticketsApiClient(
                base_url=config.qtickets_base_url,
                token=config.qtickets_token,
                logger=logger,
                org_name=config.org_name,
                dry_run=dry_run,
            )

            window_end = now_msk()
            window_start = window_end - timedelta(hours=max(since_hours, 1))

            logger.info(
                "Starting QTickets API ingestion run",
                metrics={
                    "job": job_name,
                    "since_hours": since_hours,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "dry_run": dry_run,
                    "_ver": run_version,
                },
            )

            events = client.list_events()
            orders = client.list_orders(window_start, window_end)
            clients_payload = _fetch_optional_resource(
                resource_key="clients",
                description="clients list",
                fetcher=client.list_clients,
                config=config,
                skipped=skipped_resources,
            )
            price_shades_payload = _fetch_optional_resource(
                resource_key="price_shades",
                description="price shades list",
                fetcher=client.list_price_shades,
                config=config,
                skipped=skipped_resources,
            )
            discounts_payload = _fetch_optional_resource(
                resource_key="discounts",
                description="discounts list",
                fetcher=client.list_discounts,
                config=config,
                skipped=skipped_resources,
            )
            promo_codes_payload = _fetch_optional_resource(
                resource_key="promo_codes",
                description="promo codes list",
                fetcher=client.list_promo_codes,
                config=config,
                skipped=skipped_resources,
            )
            barcodes_payload = _fetch_optional_resource(
                resource_key="barcodes",
                description="barcodes list",
                fetcher=client.list_barcodes,
                config=config,
                skipped=skipped_resources,
            )

            partner_tickets_payload: List[Dict[str, Any]] = []
            if config.should_skip("partner_tickets"):
                logger.warning(
                    "Skipping partner ticket searches: disabled via QTICKETS_SKIP_PARTNER_TICKETS",
                    metrics={"resource": "partner_tickets"},
                )
                _note_skipped_resource(
                    skipped=skipped_resources,
                    resource="partner_tickets",
                    reason="disabled_via_flag",
                )
            else:
                for request in config.partners_find_requests:
                    filter_payload = request.get("filter") or request.get("where")
                    if not isinstance(filter_payload, dict):
                        logger.warning(
                            "Skipping partner find request without valid filter",
                            metrics={"request": request},
                        )
                        continue

                    event_id = request.get("event_id")
                    show_id = request.get("show_id")

                    def _call_partner_api(
                        *,
                        _filter_payload: Dict[str, Any] = filter_payload,
                        _event_id: Any = event_id,
                        _show_id: Any = show_id,
                    ) -> List[Dict[str, Any]]:
                        return client.find_partner_tickets(
                            filter_payload=_filter_payload,
                            event_id=_event_id,
                            show_id=_show_id,
                        )

                    partner_tickets_payload.extend(
                        _fetch_optional_resource(
                            resource_key="partner_tickets",
                            description=(
                                "partner ticket search "
                                f"(event={event_id}, show={show_id})"
                            ),
                            fetcher=_call_partner_api,
                            config=config,
                            skipped=skipped_resources,
                        )
                    )

        try:
            skip_inventory = config.should_skip("inventory")
            if args.offline_fixtures_dir or skip_inventory:
                # In offline mode or when explicitly skipped, avoid seats/partners calls
                inventory_rows = []
                reason = "offline_fixtures_mode" if args.offline_fixtures_dir else "inventory_skip_flag"
                logger.info(
                    "Inventory snapshot skipped",
                    metrics={"reason": reason},
                )
            else:
                inventory_rows = build_inventory_snapshot(
                    events, client, snapshot_ts=window_end
                )
        except Exception as exc:
            logger.warning(
                "Inventory snapshot skipped due to error",
                metrics={"reason": str(exc)},
            )
            inventory_rows = []

        sales_rows = transform_orders_to_sales_rows(orders, version=run_version)
        inventory_stage_rows = _augment_inventory_rows(inventory_rows, run_version)
        events_rows = _transform_events(events, run_version)
        sales_daily_rows = _aggregate_sales_daily(sales_rows, run_version)
        sales_utm_daily_rows = _aggregate_sales_utm_daily(sales_rows, run_version)
        clients_rows = transform_clients(
            clients_payload, version=run_version, ingested_at=window_end
        )
        price_shades_rows = transform_price_shades(
            price_shades_payload, version=run_version, ingested_at=window_end
        )
        discounts_rows = transform_discounts(
            discounts_payload, version=run_version, ingested_at=window_end
        )
        promo_code_rows = transform_promo_codes(
            promo_codes_payload, version=run_version, ingested_at=window_end
        )
        barcode_rows = transform_barcodes(
            barcodes_payload, version=run_version, ingested_at=window_end
        )
        partner_ticket_rows = transform_partner_tickets(
            partner_tickets_payload, version=run_version, ingested_at=window_end
        )

        metrics = {
            "events": len(events),
            "orders": len(orders),
            "sales_rows": len(sales_rows),
            "inventory_rows": len(inventory_stage_rows),
            "sales_daily_rows": len(sales_daily_rows),
            "sales_utm_daily_rows": len(sales_utm_daily_rows),
            "clients_rows": len(clients_rows),
            "price_shades_rows": len(price_shades_rows),
            "discounts_rows": len(discounts_rows),
            "promo_code_rows": len(promo_code_rows),
            "barcode_rows": len(barcode_rows),
            "partner_ticket_rows": len(partner_ticket_rows),
        }
        metrics["lookback_hours"] = since_hours
        metrics["backfill_mode"] = backfill_mode
        metrics["rows_processed"] = (
            metrics["sales_rows"]
            + metrics["inventory_rows"]
            + metrics["sales_daily_rows"]
            + metrics["sales_utm_daily_rows"]
            + metrics["clients_rows"]
            + metrics["price_shades_rows"]
            + metrics["discounts_rows"]
            + metrics["promo_code_rows"]
            + metrics["barcode_rows"]
            + metrics["partner_ticket_rows"]
        )
        if skipped_resources:
            metrics["skipped_resources"] = skipped_resources

        if dry_run:
            logger.info(
                "Dry-run complete, no data written to ClickHouse", metrics=metrics
            )
            # Log detailed metrics in dry-run mode
            logger.info(
                "[qtickets_api] Dry-run summary",
                metrics={
                    "job": job_name,
                    "version": run_version,
                    "events_processed": metrics.get("events", 0),
                    "orders_processed": metrics.get("orders", 0),
                    "sales_rows_generated": metrics.get("sales_rows", 0),
                    "inventory_rows_generated": metrics.get("inventory_rows", 0),
                    "sales_daily_rows_generated": metrics.get("sales_daily_rows", 0),
                    "sales_utm_daily_rows_generated": metrics.get("sales_utm_daily_rows", 0),
                },
            )

            # Print concise dry-run summary
            print("[qtickets_api] Dry-run complete:")
            print(f"  Events: {metrics.get('events', 0)}")
            print(f"  Orders: {metrics.get('orders', 0)}")
            print(f"  Sales rows: {metrics.get('sales_rows', 0)}")
            print(
                f"  Inventory shows processed: {len(inventory_rows) if 'inventory_rows' in locals() else 0}"
            )
            print(f"  Sales by UTM rows: {metrics.get('sales_utm_daily_rows', 0)}")
            print(f"  Clients rows: {metrics.get('clients_rows', 0)}")
            print(f"  Price shades rows: {metrics.get('price_shades_rows', 0)}")
            print(f"  Discounts rows: {metrics.get('discounts_rows', 0)}")
            print(f"  Promo codes rows: {metrics.get('promo_code_rows', 0)}")
            print(f"  Barcode rows: {metrics.get('barcode_rows', 0)}")
            print(f"  Partner ticket rows: {metrics.get('partner_ticket_rows', 0)}")
            if skipped_resources:
                print("  Skipped resources:")
                for item in skipped_resources:
                    reason = item.get("reason") or "unspecified"
                    details = item.get("details")
                    suffix = f" ({details})" if details else ""
                    print(f"    - {item.get('resource')}: {reason}{suffix}")
            return

        if not dry_run:
            try:
                _load_clickhouse(
                    ch_client=ch_client,
                    sales_stage_rows=sales_rows,
                    inventory_stage_rows=inventory_stage_rows,
                    events_rows=events_rows,
                    sales_daily_rows=sales_daily_rows,
                    sales_utm_daily_rows=sales_utm_daily_rows,
                    clients_rows=clients_rows,
                    price_shades_rows=price_shades_rows,
                    discounts_rows=discounts_rows,
                    promo_code_rows=promo_code_rows,
                    barcode_rows=barcode_rows,
                    partner_ticket_rows=partner_ticket_rows,
                )

                _record_job_run(
                    ch_client=ch_client,
                    job=job_name,
                    status="ok",
                    started_at=started_at,
                    finished_at=now_msk(),
                    metrics=metrics,
                )

                logger.info(
                    "[qtickets_api] Ingestion completed successfully", metrics=metrics
                )
            except Exception as exc:
                logger.error(
                    f"[qtickets_api] Failed to write to ClickHouse: {exc}",
                    metrics={"error": str(exc)},
                )
                _safe_record_failure(
                    job_name,
                    started_at,
                    str(exc),
                    dry_run=False,
                    error_info={
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                )
                raise SystemExit(1)

    except (ConfigError, QticketsApiError) as exc:
        error_payload: Dict[str, Any]
        if isinstance(exc, QticketsApiError):
            error_payload = exc.as_dict()
        else:
            error_payload = {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        logger.error(
            "[qtickets_api] Configuration or API error",
            metrics={"error": str(exc), **{k: v for k, v in error_payload.items() if k != "message"}},
        )
        _safe_record_failure(
            job_name,
            started_at,
            str(exc),
            dry_run=dry_run,
            error_info=error_payload,
        )
        raise SystemExit(1)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[qtickets_api] Unexpected failure during ingestion",
            metrics={"error": str(exc)},
        )
        _safe_record_failure(
            job_name,
            started_at,
            str(exc),
            dry_run=dry_run,
            error_info={
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            },
        )
        raise SystemExit(1)


# --------------------------------------------------------------------- #
# ClickHouse loaders
# --------------------------------------------------------------------- #
def _load_clickhouse(
    *,
    ch_client: ClickHouseClient | None,
    sales_stage_rows: Sequence[Dict[str, Any]],
    inventory_stage_rows: Sequence[Dict[str, Any]],
    events_rows: Sequence[Dict[str, Any]],
    sales_daily_rows: Sequence[Dict[str, Any]],
    sales_utm_daily_rows: Sequence[Dict[str, Any]],
    clients_rows: Sequence[Dict[str, Any]],
    price_shades_rows: Sequence[Dict[str, Any]],
    discounts_rows: Sequence[Dict[str, Any]],
    promo_code_rows: Sequence[Dict[str, Any]],
    barcode_rows: Sequence[Dict[str, Any]],
    partner_ticket_rows: Sequence[Dict[str, Any]],
) -> None:
    """Persist staging and fact tables to ClickHouse."""
    if ch_client is None:
        logger.info("Skipping ClickHouse load: no client (dry-run mode)")
        return

    # Use zakaz_test for local testing
    database_prefix = (
        "zakaz_test" if os.getenv("CH_DATABASE") == "zakaz_test" else "zakaz"
    )

    if sales_stage_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_orders_raw", list(sales_stage_rows)
        )

    if inventory_stage_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_inventory_raw",
            list(inventory_stage_rows),
        )

    if events_rows:
        ch_client.insert(f"{database_prefix}.dim_events", list(events_rows))

    if sales_daily_rows:
        ch_client.insert(
            f"{database_prefix}.fact_qtickets_sales_daily", list(sales_daily_rows)
        )

    if sales_utm_daily_rows:
        ch_client.insert(
            f"{database_prefix}.fact_qtickets_sales_utm_daily",
            list(sales_utm_daily_rows),
        )

    if clients_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_clients_raw",
            list(clients_rows),
        )

    if price_shades_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_price_shades_raw",
            list(price_shades_rows),
        )

    if discounts_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_discounts_raw",
            list(discounts_rows),
        )

    if promo_code_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_promo_codes_raw",
            list(promo_code_rows),
        )

    if barcode_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_barcodes_raw",
            list(barcode_rows),
        )

    if partner_ticket_rows:
        ch_client.insert(
            f"{database_prefix}.stg_qtickets_api_partner_tickets_raw",
            list(partner_ticket_rows),
        )

    if inventory_stage_rows:
        # Use same rows with _ver to update the latest snapshot fact table.
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
        ch_client.insert(
            f"{database_prefix}.fact_qtickets_inventory_latest", latest_rows
        )


def _record_job_run(
    *,
    ch_client: ClickHouseClient | None,
    job: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    metrics: Dict[str, Any],
    error: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a meta_job_runs entry."""
    if ch_client is None:
        logger.info("Skipping job run recording: no client (dry-run mode)")
        return

    base_metrics = metrics or {}
    rows_processed = base_metrics.get("rows_processed")
    if rows_processed is None:
        rows_processed = int(
            base_metrics.get("sales_rows", 0)
            + base_metrics.get("inventory_rows", 0)
            + base_metrics.get("sales_daily_rows", 0)
            + base_metrics.get("sales_utm_daily_rows", 0)
            + base_metrics.get("clients_rows", 0)
            + base_metrics.get("price_shades_rows", 0)
            + base_metrics.get("discounts_rows", 0)
            + base_metrics.get("promo_code_rows", 0)
            + base_metrics.get("barcode_rows", 0)
            + base_metrics.get("partner_ticket_rows", 0)
        )

    message_payload: Dict[str, Any] = {"status": status}
    for key in (
        "orders",
        "events",
        "sales_rows",
        "inventory_rows",
        "sales_daily_rows",
        "sales_utm_daily_rows",
        "clients_rows",
        "price_shades_rows",
        "discounts_rows",
        "promo_code_rows",
        "barcode_rows",
        "partner_ticket_rows",
    ):
        if key in base_metrics:
            message_payload[key] = base_metrics[key]
    skipped_info = base_metrics.get("skipped_resources")
    if skipped_info:
        message_payload["skipped_resources"] = skipped_info
    if error:
        message_payload["error"] = error

    payload = {
        "job": job,
        "started_at": started_at.replace(tzinfo=None),
        "finished_at": finished_at.replace(tzinfo=None),
        "rows_processed": int(rows_processed),
        "status": status,
        "message": json.dumps(message_payload, ensure_ascii=False),
        "metrics": json.dumps(base_metrics, ensure_ascii=False),
    }
    database_prefix = (
        "zakaz_test" if os.getenv("CH_DATABASE") == "zakaz_test" else "zakaz"
    )
    ch_client.insert(f"{database_prefix}.meta_job_runs", [payload])


def _fetch_optional_resource(
    *,
    resource_key: str,
    description: str,
    fetcher: Callable[[], Optional[Sequence[Dict[str, Any]]]],
    config: QticketsApiConfig,
    skipped: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Retrieve optional datasets best-effort, logging warnings on non-fatal errors.
    """
    if config.should_skip(resource_key):
        logger.warning(
            "Skipping %s: disabled via configuration flag",
            description,
            metrics={"resource": resource_key},
        )
        _note_skipped_resource(
            skipped=skipped,
            resource=resource_key,
            reason="disabled_via_flag",
        )
        return []

    try:
        payload = fetcher() or []
    except QticketsApiError as exc:
        if exc.status in NON_FATAL_HTTP_STATUSES:
            logger.warning(
                "Skipping %s: API returned %s",
                description,
                exc.status,
                metrics={"resource": resource_key, **exc.as_dict()},
            )
            _note_skipped_resource(
                skipped=skipped,
                resource=resource_key,
                reason=f"http_{exc.status}",
                details=exc.as_dict(),
            )
            return []
        raise

    return list(payload)


def _note_skipped_resource(
    *,
    skipped: List[Dict[str, Any]],
    resource: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append structured metadata about skipped datasets."""
    entry: Dict[str, Any] = {"resource": resource, "reason": reason}
    if details:
        entry["details"] = details
    skipped.append(entry)


def _safe_record_failure(
    job: str,
    started_at: datetime,
    message: str,
    *,
    dry_run: bool,
    error_info: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record job failure in ClickHouse when possible without raising secondary errors.

    The function loads configuration from environment variables. It never raises to keep
    the original exception visible.
    """
    if dry_run:
        logger.warning(
            "Skipping failure recording because the loader was invoked with --dry-run",
            metrics={"job": job, "error": message},
        )
        return

    try:
        # Try to load config from environment and create client
        config = QticketsApiConfig.load()
        ch_client = get_client_from_config(config)
        _record_job_run(
            ch_client=ch_client,
            job=job,
            status="error",
            started_at=started_at,
            finished_at=now_msk(),
            metrics={"error": message, "error_details": error_info or {}},
            error=error_info,
        )
    except ConfigError as exc:
        logger.warning(
            "Skipping failure recording: configuration is not available",
            metrics={"job": job, "error": message, "config_error": str(exc)},
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Unable to record failure in meta_job_runs",
            metrics={"job": job, "error": message, "secondary_error": str(exc)},
        )


def _load_fixtures(directory: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load offline fixtures for events and orders."""
    base = Path(directory)
    if not base.exists():
        raise FileNotFoundError(f"Fixtures directory does not exist: {directory}")

    def _read_json(candidates: Sequence[str]) -> List[Dict[str, Any]]:
        for filename in candidates:
            path = base / filename
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                    if isinstance(payload, list):
                        return [item for item in payload if isinstance(item, dict)]
                    if isinstance(payload, dict) and isinstance(
                        payload.get("data"), list
                    ):
                        return [
                            item for item in payload["data"] if isinstance(item, dict)
                        ]
                break
        raise FileNotFoundError(
            f"Expected one of {', '.join(candidates)} in {directory}"
        )

    events = _read_json(
        ["events.json", "events_sample.json", "events_fixture.json"]
    )
    orders = _read_json(
        ["orders.json", "orders_sample.json", "orders_fixture.json"]
    )
    return events, orders


# --------------------------------------------------------------------- #
# Transform helpers
# --------------------------------------------------------------------- #
def _augment_inventory_rows(
    rows: Sequence[Dict[str, Any]], version: int
) -> List[Dict[str, Any]]:
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


def _transform_events(
    events: Sequence[Dict[str, Any]], version: int
) -> List[Dict[str, Any]]:
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
                "event_name": (
                    event.get("name") or event.get("event_name") or ""
                ).strip(),
                "city": str(event.get("city") or "").strip().lower(),
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


def _aggregate_sales_daily(
    rows: Sequence[Dict[str, Any]], version: int
) -> List[Dict[str, Any]]:
    """Roll raw sales rows by day/event/city."""
    buckets: Dict[tuple, Dict[str, Any]] = defaultdict(
        lambda: {"tickets_sold": 0, "revenue": 0.0}
    )

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


def _aggregate_sales_utm_daily(
    rows: Sequence[Dict[str, Any]], version: int
) -> List[Dict[str, Any]]:
    """Roll raw sales rows by day/event/city/UTM."""
    buckets: Dict[tuple, Dict[str, Any]] = defaultdict(
        lambda: {"tickets_sold": 0, "revenue": 0.0}
    )

    for row in rows:
        sale_ts = row.get("sale_ts")
        if not isinstance(sale_ts, datetime):
            continue

        key = (
            row.get("event_id"),
            row.get("city"),
            sale_ts.date(),
            row.get("utm_source") or "",
            row.get("utm_medium") or "",
            row.get("utm_campaign") or "",
            row.get("utm_content") or "",
            row.get("utm_term") or "",
        )
        bucket = buckets[key]
        bucket["tickets_sold"] += int(row.get("tickets_sold", 0))
        bucket["revenue"] += float(row.get("revenue", 0))

    aggregated: List[Dict[str, Any]] = []
    for (
        event_id,
        city,
        sales_date,
        utm_source,
        utm_medium,
        utm_campaign,
        utm_content,
        utm_term,
    ), values in buckets.items():
        aggregated.append(
            {
                "sales_date": sales_date,
                "event_id": event_id,
                "city": city,
                "utm_source": utm_source,
                "utm_medium": utm_medium,
                "utm_campaign": utm_campaign,
                "utm_content": utm_content,
                "utm_term": utm_term,
                "tickets_sold": int(values["tickets_sold"]),
                "revenue": float(values["revenue"]),
                "_ver": int(version),
            }
        )

    return aggregated


if __name__ == "__main__":
    main()

