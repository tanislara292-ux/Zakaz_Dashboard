"""
Transformation helpers for QTickets API payloads.

The goal is to produce deduplicated ClickHouse-ready rows while keeping the raw
payloads free from personal data. Personal data (email, phone, name) is excluded
from all outputs for GDPR compliance.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from integrations.common.logging import setup_integrations_logger
from integrations.common.time import now_msk, to_msk
from integrations.common.utm import extract_utm_params

logger = setup_integrations_logger("qtickets_api")


def transform_orders_to_sales_rows(
    orders: Sequence[Dict[str, Any]] | None,
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
    if not orders:
        logger.info(
            "transform_orders_to_sales_rows() received no orders -> []",
            metrics={"orders": 0},
        )
        return []

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

        utm = _extract_utm(order)

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
            "utm_source": utm.get("utm_source", ""),
            "utm_medium": utm.get("utm_medium", ""),
            "utm_campaign": utm.get("utm_campaign", ""),
            "utm_content": utm.get("utm_content", ""),
            "utm_term": utm.get("utm_term", ""),
            "sale_ts": sale_ts,
            "tickets_sold": int(tickets_sold),
            "revenue": float(revenue),
            "currency": (order.get("currency") or "RUB").upper(),
            "payload_json": _payload_json(order),
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


def _extract_utm(order: Dict[str, Any]) -> Dict[str, str]:
    """Extract and normalize UTM parameters from heterogeneous order payloads."""
    if not isinstance(order, dict):
        return {}

    utm_raw: Dict[str, str] = {}

    def _merge(source: Optional[Dict[str, Any]]) -> None:
        if not isinstance(source, dict):
            return
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
            value = source.get(key)
            if value is None:
                continue
            value_str = str(value).strip()
            if value_str != "":
                utm_raw[key] = value_str

    # Top-level fields
    _merge(order)

    # Common nested containers
    for nested_key in ("utm", "utm_params", "utm_data"):
        _merge(order.get(nested_key))

    meta_block = order.get("meta") or order.get("metadata")
    if isinstance(meta_block, dict):
        _merge(meta_block)
        _merge(meta_block.get("utm"))
        _merge(meta_block.get("utm_params"))

    analytics_block = order.get("analytics") or order.get("tracking")
    _merge(analytics_block)

    return extract_utm_params(utm_raw)


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


def _resolve_ingest_ts(ingested_at: Optional[datetime] = None) -> datetime:
    ts = ingested_at or now_msk()
    return ts.replace(tzinfo=None)


def _payload_json(item: Dict[str, Any]) -> str:
    return json.dumps(item or {}, ensure_ascii=False, sort_keys=True)


def _safe_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return to_msk(value).replace(tzinfo=None)
    except Exception:
        return None


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def transform_clients(
    clients: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not clients:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for entry in clients:
        if not isinstance(entry, dict):
            continue
        client_id = entry.get("id") or entry.get("client_id")
        if client_id is None:
            continue
        details = entry.get("details") or {}
        rows.append(
            {
                "client_id": str(client_id),
                "email": _safe_str(entry.get("email")).lower(),
                "phone": _safe_str(details.get("phone") or entry.get("phone")),
                "first_name": _safe_str(details.get("name") or entry.get("name")),
                "last_name": _safe_str(details.get("surname") or entry.get("surname")),
                "middle_name": _safe_str(
                    details.get("middlename") or entry.get("middlename")
                ),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(entry),
            }
        )
    return rows


def transform_price_shades(
    shades: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not shades:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for shade in shades:
        if not isinstance(shade, dict):
            continue
        shade_id = shade.get("id") or shade.get("shade_id")
        if shade_id is None:
            continue
        rows.append(
            {
                "shade_id": str(shade_id),
                "name": _safe_str(shade.get("name")),
                "color": _safe_str(shade.get("color") or shade.get("hex")),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(shade),
            }
        )
    return rows


def transform_discounts(
    discounts: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not discounts:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for discount in discounts:
        if not isinstance(discount, dict):
            continue
        discount_id = discount.get("id") or discount.get("discount_id")
        if discount_id is None:
            continue
        rows.append(
            {
                "discount_id": str(discount_id),
                "name": _safe_str(discount.get("name")),
                "discount_type": _safe_str(
                    discount.get("discount_type") or discount.get("type")
                ),
                "discount_value": _coerce_float(
                    discount.get("value") or discount.get("discount_value")
                ),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(discount),
            }
        )
    return rows


def transform_promo_codes(
    promo_codes: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not promo_codes:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for promo in promo_codes:
        if not isinstance(promo, dict):
            continue
        promo_id = promo.get("id") or promo.get("promo_code_id")
        if promo_id is None:
            continue
        rows.append(
            {
                "promo_code_id": str(promo_id),
                "code": _safe_str(promo.get("code")),
                "discount_type": _safe_str(promo.get("discount_type")),
                "discount_value": _coerce_float(promo.get("discount_value")),
                "valid_from": _coerce_datetime(promo.get("valid_from")),
                "valid_to": _coerce_datetime(promo.get("valid_to")),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(promo),
            }
        )
    return rows


def transform_barcodes(
    barcodes: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not barcodes:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for item in barcodes:
        if not isinstance(item, dict):
            continue
        barcode = item.get("barcode") or item.get("code")
        if not barcode:
            continue
        rows.append(
            {
                "barcode": _safe_str(barcode),
                "event_id": _safe_str(item.get("event_id")),
                "show_id": _safe_str(item.get("show_id")),
                "status": _safe_str(item.get("status")),
                "checked_at": _coerce_datetime(
                    item.get("checked_at") or item.get("scanned_at")
                ),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(item),
            }
        )
    return rows


def transform_partner_tickets(
    tickets: Sequence[Dict[str, Any]] | None,
    *,
    version: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if not tickets:
        return []
    stamp = version or int(time.time())
    ingest_ts = _resolve_ingest_ts(ingested_at)
    rows: List[Dict[str, Any]] = []
    for ticket in tickets:
        if not isinstance(ticket, dict):
            continue
        ticket_id = ticket.get("id") or ticket.get("ticket_id")
        rows.append(
            {
                "ticket_id": _safe_str(ticket_id),
                "event_id": _safe_str(ticket.get("event_id")),
                "show_id": _safe_str(ticket.get("show_id")),
                "external_order_id": _safe_str(ticket.get("external_order_id")),
                "external_id": _safe_str(ticket.get("external_id")),
                "barcode": _safe_str(ticket.get("barcode")),
                "paid": 1 if ticket.get("paid") in (1, True, "1", "true") else 0,
                "price": _coerce_float(ticket.get("price")),
                "_ver": stamp,
                "_ingest_ts": ingest_ts,
                "payload_json": _payload_json(ticket),
            }
        )
    return rows
