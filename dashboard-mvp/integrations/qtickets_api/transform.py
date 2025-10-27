"""
Transformation helpers for QTickets API payloads.

The goal is to produce deduplicated ClickHouse-ready rows while keeping the raw
payloads free from personal data. Personal data (email, phone, name) is excluded
from all outputs for GDPR compliance.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from integrations.common.logging import setup_integrations_logger
from integrations.common.time import to_msk

logger = setup_integrations_logger("qtickets_api")


def transform_orders_to_sales_rows(
    orders: Sequence[Dict[str, Any]],
    *,
    version: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Convert QTickets orders into ClickHouse fact rows.

    Args:
        orders: Raw orders returned by :meth:`QticketsApiClient.fetch_orders_get`.
        version: Explicit version stamp for ReplacingMergeTree.  Defaults to the
            current Unix timestamp.

    Notes:
        - Personal data (email, phone, customer name) is explicitly excluded
        - Only paid orders are processed (payed = 1 or payed_at present)
        - Revenue calculation excludes refunds and cancellations
    """
    run_version = version or int(time.time())
    rows: List[Dict[str, Any]] = []

    for order in orders:
        if not order:
            continue

        # Check if order is paid - support both boolean and integer representations
        is_paid = order.get("payed") or order.get("paid")
        if is_paid not in [1, True, "1", "true"]:
            continue

        # Extract order ID - support multiple field names
        order_id = order.get("id") or order.get("order_id")
        if not order_id:
            logger.warning(
                "Skipping order without order_id",
                metrics={"order": str(order)[:100]},  # Truncate for logging
            )
            continue

        # Extract basket/order items - support multiple field names
        baskets = (
            order.get("baskets") or order.get("items") or order.get("order_items") or []
        )
        if not isinstance(baskets, Iterable):
            baskets = []

        # Calculate tickets sold and revenue
        tickets_sold = _count_tickets(baskets)
        revenue = _sum_revenue(baskets)

        # Extract payment timestamp - support multiple field names
        sale_ts_raw = (
            order.get("payed_at") or order.get("paid_at") or order.get("created_at")
        )
        if not sale_ts_raw:
            logger.warning(
                "Skipping order without payment timestamp",
                metrics={"order_id": order_id},
            )
            continue

        try:
            sale_ts = to_msk(sale_ts_raw).replace(tzinfo=None)
        except Exception as e:
            logger.warning(
                "Skipping order with unparsable payment timestamp",
                metrics={
                    "order_id": order_id,
                    "sale_ts_raw": str(sale_ts_raw)[:50],
                    "error": str(e),
                },
            )
            continue

        # Extract event ID with enhanced logic
        event_id = _extract_event_id(order, baskets)
        if not event_id:
            logger.warning(
                "Skipping order without event_id",
                metrics={"order_id": order_id},
            )
            continue

        # Extract city with enhanced logic
        city = (
            (
                order.get("city")
                or (order.get("event") or {}).get("city")
                or _extract_city(baskets)
                or ""
            )
            .strip()
            .lower()
        )

        # Create the record for ClickHouse
        record = {
            "order_id": str(order_id),
            "event_id": str(event_id),
            "city": city,
            "sale_ts": sale_ts,
            "tickets_sold": int(tickets_sold),
            "revenue": float(revenue),
            "currency": (order.get("currency") or "RUB").upper(),
            "_ver": int(run_version),
            "_dedup_key": _dedup_key(
                order_id=order_id,
                event_id=event_id,
                sale_ts=sale_ts,
                revenue=revenue,
            ),
        }

        rows.append(record)

    logger.info(
        "Transformed orders into sales rows",
        metrics={
            "orders": len(orders),
            "rows": len(rows),
            "_ver": run_version,
        },
    )
    return rows


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
def _count_tickets(baskets: Iterable[Dict[str, Any]]) -> int:
    """Return the number of tickets sold within the order."""
    count = 0
    for item in baskets:
        if not isinstance(item, dict):
            continue

        # Skip refunds and cancellations
        if (
            item.get("status") == "refund"
            or item.get("is_refund")
            or item.get("status") == "cancelled"
            or item.get("cancelled_at")
        ):
            continue

        # Count tickets - support quantity field or count as 1 per item
        quantity = item.get("quantity") or item.get("count") or item.get("amount") or 1
        try:
            count += int(quantity)
        except (ValueError, TypeError):
            # Default to 1 if quantity is not parseable
            count += 1

    return count


def _sum_revenue(baskets: Iterable[Dict[str, Any]]) -> float:
    """Aggregate revenue by summing ticket prices within the order."""
    total = 0.0
    for item in baskets:
        if not isinstance(item, dict):
            continue

        # Skip refunds and cancellations
        if (
            item.get("status") == "refund"
            or item.get("is_refund")
            or item.get("status") == "cancelled"
            or item.get("cancelled_at")
        ):
            continue

        # Extract price - support multiple field names
        price = (
            item.get("price")
            or item.get("cost")
            or item.get("amount")
            or item.get("total")
            or 0
        )

        quantity = item.get("quantity") or item.get("count") or 1

        try:
            item_total = float(price) * float(quantity)
            total += item_total
        except (TypeError, ValueError):
            continue

    return total


def _extract_event_id(
    order: Dict[str, Any], baskets: Iterable[Dict[str, Any]]
) -> Optional[Any]:
    """Derive the event identifier from the order or basket payload."""
    # Direct fields in order
    if order.get("event_id"):
        return order["event_id"]
    if order.get("show_id"):
        return order["show_id"]

    # Nested event object
    event = order.get("event") or order.get("show")
    if isinstance(event, dict):
        if event.get("id"):
            return event["id"]
        if event.get("event_id"):
            return event["event_id"]
        if event.get("show_id"):
            return event["show_id"]

    # Extract from basket items
    for item in baskets:
        if not isinstance(item, dict):
            continue
        if item.get("event_id"):
            return item["event_id"]
        if item.get("show_id"):
            return item["show_id"]

        # Nested event in basket
        event_info = item.get("event") or item.get("show")
        if isinstance(event_info, dict):
            if event_info.get("id"):
                return event_info["id"]
            if event_info.get("event_id"):
                return event_info["event_id"]
            if event_info.get("show_id"):
                return event_info["show_id"]

    return None


def _extract_city(baskets: Iterable[Dict[str, Any]]) -> Optional[str]:
    """Best-effort extraction of the event city from basket details."""
    for item in baskets:
        if not isinstance(item, dict):
            continue
        # Support multiple nested structures
        event_info = item.get("event") or item.get("show") or {}
        if isinstance(event_info, dict):
            city = event_info.get("city")
            if city:
                return str(city).strip()

        # Also check venue/place info
        venue = item.get("venue") or item.get("place") or {}
        if isinstance(venue, dict):
            city = venue.get("city")
            if city:
                return str(city).strip()

    return None


def _dedup_key(
    *,
    order_id: Any,
    event_id: Any,
    sale_ts: Any,
    revenue: Any,
) -> str:
    """Build an md5 hash for ReplacingMergeTree deduplication."""
    key_parts = [
        str(order_id or ""),
        str(event_id or ""),
        str(sale_ts or ""),
        str(revenue or ""),
    ]
    digest = hashlib.md5("::".join(key_parts).encode("utf-8")).hexdigest()
    return digest
