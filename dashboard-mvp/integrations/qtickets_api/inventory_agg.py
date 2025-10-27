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
    client: QticketsApiClient,
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
        List of dictionaries ready for ClickHouse staging.

    Raises:
        NotImplementedError: when show identifiers cannot be derived.
    """
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
        if not show_ids:
            raise NotImplementedError(
                "Unable to derive show identifiers for event "
                f"{event_id}. Request the QTickets vendor to clarify the "
                "show/session API so that seat availability can be aggregated."
            )

        total = 0
        left = 0

        for show_id in show_ids:
            seats_response = client.get_seats(show_id)

            # Handle the real API structure with zones and admission flags
            if isinstance(seats_response, dict) and "data" in seats_response:
                # Real format: {"data": {"zone_id": {"zone_id": "...", "name": "...", "seats": {...}}} }
                zones = seats_response["data"]
                for zone_key, zone_data in zones.items():
                    if isinstance(zone_data, dict):
                        zone_seats = zone_data.get("seats", {})
                        # Count all unique seats in the zone
                        total += len(zone_seats)
                        # Count available seats (admission == true)
                        available = sum(
                            1
                            for seat_key, seat_info in zone_seats.items()
                            if isinstance(seat_info, dict)
                            and seat_info.get("admission") is True
                        )
                        left += available
            else:
                # Fallback to old format if structure changes
                logger.warning(
                    "Unexpected seats response format, using fallback counting",
                    metrics={
                        "event_id": event_id,
                        "show_id": show_id,
                        "response_type": type(seats_response).__name__,
                    },
                )
                for seat in seats_response:
                    # Try to extract counts from seat data
                    if isinstance(seat, dict):
                        total += 1
                        if seat.get("admission") is True:
                            left += 1

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
