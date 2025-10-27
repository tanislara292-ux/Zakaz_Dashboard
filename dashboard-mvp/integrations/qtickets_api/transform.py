"""
Transformation helpers for QTickets API payloads.

The goal is to produce deduplicated ClickHouse-ready rows while keeping the raw
payloads free from personal data.
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
        orders: Raw orders returned by :meth:`QticketsApiClient.list_orders`.
        version: Explicit version stamp for ReplacingMergeTree.  Defaults to the
            current Unix timestamp.
    """
    run_version = version or int(time.time())
    rows: List[Dict[str, Any]] = []

    for order in orders:
        if not order or not order.get("payed"):
            continue

        baskets = order.get("baskets") or []
        if not isinstance(baskets, Iterable):
            baskets = []

        tickets_sold = _count_tickets(baskets)
        revenue = _sum_revenue(baskets)

        sale_ts_raw = order.get("payed_at") or order.get("paid_at")
        if not sale_ts_raw:
            logger.warning(
                "Skipping order without payed_at",
                metrics={"order_id": order.get("id")},
            )
            continue

        try:
            sale_ts = to_msk(sale_ts_raw).replace(tzinfo=None)
        except Exception:
            logger.warning(
                "Skipping order with unparsable payed_at",
                metrics={"order_id": order.get("id"), "payed_at": sale_ts_raw},
            )
            continue

        event_id = _extract_event_id(order, baskets)
        if not event_id:
            raise ValueError(
                f"Unable to determine event_id for order {order.get('id')}. "
                "Inspect the API payload and extend the transformer mapping."
            )

        city = (
            order.get("city")
            or (order.get("event") or {}).get("city")
            or _extract_city(baskets)
            or ""
        )

        record = {
            "event_id": str(event_id),
            "city": city.strip().lower(),
            "sale_ts": sale_ts,
            "tickets_sold": int(tickets_sold),
            "revenue": float(revenue),
            "currency": (order.get("currency") or "RUB").upper(),
            "_ver": int(run_version),
            "_dedup_key": _dedup_key(
                order_id=order.get("id"),
                event_id=event_id,
                sale_ts=sale_ts,
                revenue=revenue,
            ),
        }

        rows.append(record)

    logger.info(
        "Transformed orders into sales rows",
        metrics={"orders": len(orders), "rows": len(rows), "_ver": run_version},
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
        # Ignore refunds or zero-quantity items if the API exposes those flags.
        if item.get("status") == "refund":
            continue
        if item.get("is_refund"):
            continue
        count += 1
    return count


def _sum_revenue(baskets: Iterable[Dict[str, Any]]) -> float:
    """Aggregate revenue by summing ticket prices within the order."""
    total = 0.0
    for item in baskets:
        if not isinstance(item, dict):
            continue
        if item.get("status") == "refund" or item.get("is_refund"):
            continue
        try:
            total += float(item.get("price") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _extract_event_id(order: Dict[str, Any], baskets: Iterable[Dict[str, Any]]) -> Optional[Any]:
    """Derive the event identifier from the order or basket payload."""
    if order.get("event_id"):
        return order["event_id"]

    event = order.get("event")
    if isinstance(event, dict) and event.get("id"):
        return event["id"]

    for item in baskets:
        if not isinstance(item, dict):
            continue
        if item.get("event_id"):
            return item["event_id"]
        event_info = item.get("event")
        if isinstance(event_info, dict) and event_info.get("id"):
            return event_info["id"]

    return None


def _extract_city(baskets: Iterable[Dict[str, Any]]) -> Optional[str]:
    """Best-effort extraction of the event city from basket details."""
    for item in baskets:
        if not isinstance(item, dict):
            continue
        event_info = item.get("event") or {}
        if isinstance(event_info, dict):
            city = event_info.get("city")
            if city:
                return city
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
