"""
Inventory aggregation helpers for the QTickets API integration.

The API exposes seat availability per show (session) through the
/ shows/{show_id}/seats endpoint. The real API returns a structure with zones
containing seats with admission flags, not direct counts. This module adapts
to this format and rolls up to event-level snapshots for ClickHouse ingestion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence

from integrations.common.logging import setup_integrations_logger
from integrations.common.time import now_msk

from .client import QticketsApiClient

logger = setup_integrations_logger("qtickets_api")


def build_inventory_snapshot(
    events: Sequence[Dict[str, Any]],
    client: QticketsApiClient | None,
    *,
    snapshot_ts: datetime | None = None,
) -> List[Dict[str, Any]]:
    """
    Collapse seat availability into per-event snapshots.

    Args:
        events: Raw events payload returned by :meth:`QticketsApiClient.list_events`.
        client: API client used to fetch seat allocations per show.
        snapshot_ts: Optional explicit timestamp in MSK.  Defaults to ``now``.

    Returns:
        List of dictionaries ready for ClickHouse staging. Empty when the client
        operates in stub mode or events lack show identifiers.
    """
    if client is None:
        logger.warning("Inventory snapshot skipped: API client is not available")
        return []

    if getattr(client, "stub_mode", False):
        logger.warning(
            "Inventory snapshot skipped: client operates in stub mode",
            metrics={"org": getattr(client, "org_name", None)},
        )
        return []

    snapshot_ts = snapshot_ts or now_msk()
    snapshot_naive = snapshot_ts.replace(tzinfo=None)

    inventory_rows: List[Dict[str, Any]] = []
    for event in events:
        event_id = event.get("id") or event.get("event_id")
        event_name = event.get("name") or event.get("event_name") or ""
        city_value = event.get("city") or ""
        city = str(city_value).strip().lower()

        if not event_id:
            logger.warning("Skipping event without identifier in inventory aggregation")
            continue

        show_ids = _extract_show_ids(event)

        total, left = _summarize_seat_payload(client.list_event_seats(event_id))

        if total == 0 and show_ids:
            for show_id in show_ids:
                try:
                    payload = client.get_event_show_seats(event_id, show_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch show seats from REST API",
                        metrics={
                            "event_id": event_id,
                            "show_id": show_id,
                            "error": str(exc),
                        },
                    )
                    continue
                sub_total, sub_left = _summarize_seat_payload(payload)
                total += sub_total
                left += sub_left

        if total == 0 and getattr(client, "partners_ready", False):
            payload = client.partners_event_seats(event_id)
            total, left = _summarize_seat_payload(payload)
            if total == 0 and show_ids:
                for show_id in show_ids:
                    payload = client.partners_event_seats(event_id, show_id)
                    sub_total, sub_left = _summarize_seat_payload(payload)
                    total += sub_total
                    left += sub_left

        # Log inventory metrics for debugging
        logger.info(
            "Calculated inventory for event",
            metrics={
                "event_id": event_id,
                "event_name": event_name[:50],  # Truncate for logging
                "city": city,
                "shows_processed": len(show_ids),
                "tickets_total": total,
                "tickets_left": left,
            },
        )

        inventory_rows.append(
            {
                "event_id": str(event_id),
                "event_name": event_name,
                "city": city,
                "snapshot_ts": snapshot_naive,
                "tickets_total": int(total) if total > 0 else None,
                "tickets_left": int(left) if left > 0 else None,
            }
        )

    logger.info(
        "Built inventory snapshot",
        metrics={"events_processed": len(inventory_rows)},
    )
    return inventory_rows


def _extract_show_ids(event: Dict[str, Any]) -> List[Any]:
    """Extract show identifiers from the event payload if available."""
    candidate_keys = ("shows", "sessions", "seances")

    show_ids: List[Any] = []
    for key in candidate_keys:
        shows = event.get(key)
        if not isinstance(shows, Iterable):
            continue
        for item in shows:
            if isinstance(item, dict):
                if "show_id" in item:
                    show_ids.append(item["show_id"])
                elif "id" in item:
                    show_ids.append(item["id"])
            elif item is not None:
                show_ids.append(item)

    # Deduplicate while preserving order.
    seen: set[Any] = set()
    unique_ids: List[Any] = []
    for show_id in show_ids:
        if show_id in seen:
            continue
        seen.add(show_id)
        unique_ids.append(show_id)

    return unique_ids


def _summarize_seat_payload(payload: Any) -> tuple[int, int]:
    """Calculate total and available seats from heterogeneous payloads."""
    total = 0
    available = 0
    seen: set[str] = set()
    for seat in _iter_seat_nodes(payload):
        if not isinstance(seat, dict):
            continue
        seat_id_raw = seat.get("seat_id") or seat.get("id")
        seat_id = str(seat_id_raw) if seat_id_raw is not None else None
        if seat_id and seat_id in seen:
            continue
        if seat_id:
            seen.add(seat_id)
        total += 1
        if _seat_available(seat):
            available += 1
    return total, available


def _seat_available(seat: Dict[str, Any]) -> bool:
    flags = (
        seat.get("available"),
        seat.get("admission"),
        seat.get("is_free"),
    )
    for flag in flags:
        if flag in (True, 1, "1", "true", "True"):
            return True
    return False


def _iter_seat_nodes(payload: Any) -> Iterable[Dict[str, Any]]:
    """Yield seat dictionaries from nested seat responses."""
    if payload is None:
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _iter_seat_nodes(item)
        return

    if not isinstance(payload, dict):
        return

    # Direct seat representation
    if any(key in payload for key in ("seat_id", "available", "admission")):
        yield payload

    # Zones array
    zones = payload.get("zones")
    if isinstance(zones, list):
        for zone in zones:
            yield from _iter_seat_nodes(zone)

    # Seats mapping/array
    seats = payload.get("seats")
    if isinstance(seats, dict):
        for seat in seats.values():
            if isinstance(seat, dict):
                yield from _iter_seat_nodes(seat)
    elif isinstance(seats, list):
        for seat in seats:
            yield from _iter_seat_nodes(seat)

    # Offers dictionary
    offers = payload.get("offers")
    if isinstance(offers, dict):
        for offer in offers.values():
            if isinstance(offer, dict):
                yield from _iter_seat_nodes(offer)

    # Nested data blocks
    data = payload.get("data")
    if isinstance(data, dict) or isinstance(data, list):
        yield from _iter_seat_nodes(data)
