"""
Inventory aggregation helpers for the QTickets API integration.

The API exposes seat availability per show (session).  This module rolls these
records up to an event-level snapshot suitable for ClickHouse ingestion.
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
        city = (event.get("city") or "").strip().lower()

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
            seats = client.get_seats(show_id)
            for seat in seats:
                total += int(seat.get("max_count") or 0)
                left += int(seat.get("free_count") or 0)

        inventory_rows.append(
            {
                "event_id": str(event_id),
                "event_name": event_name,
                "city": city,
                "snapshot_ts": snapshot_naive,
                "tickets_total": int(total),
                "tickets_left": int(left),
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
