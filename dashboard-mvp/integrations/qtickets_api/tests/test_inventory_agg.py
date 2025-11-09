from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

from integrations.qtickets_api.inventory_agg import (
    build_inventory_snapshot,
    _summarize_seat_payload,
)


def test_build_inventory_snapshot_aggregates_rest_payload():
    client = Mock()
    client.stub_mode = False
    client.partners_ready = False
    client.list_event_seats.return_value = {
        "zones": [
            {
                "zone_id": 1,
                "seats": [
                    {"seat_id": "A-1", "available": True},
                    {"seat_id": "A-2", "available": False},
                ],
            }
        ]
    }
    events = [{"id": 123, "name": "Test Event", "city": "moscow"}]
    snapshot_ts = datetime(2025, 1, 1, 12, 0, 0)

    rows = build_inventory_snapshot(events, client, snapshot_ts=snapshot_ts)

    assert len(rows) == 1
    assert rows[0]["event_id"] == "123"
    assert rows[0]["tickets_total"] == 2
    assert rows[0]["tickets_left"] == 1
    assert rows[0]["snapshot_ts"] == snapshot_ts


def test_build_inventory_snapshot_uses_partner_fallback():
    client = Mock()
    client.stub_mode = False
    client.partners_ready = True
    client.list_event_seats.return_value = {}  # REST payload empty
    client.get_event_show_seats.return_value = {}
    client.partners_event_seats.side_effect = [
        {},  # event-level partner response empty
        {"seats": {"P-1": {"seat_id": "P-1", "admission": True}}},
    ]
    events = [{"id": "E1", "name": "Partner Event", "shows": [{"show_id": "S1"}]}]
    snapshot_ts = datetime(2025, 1, 2, 10, 0, 0)

    rows = build_inventory_snapshot(events, client, snapshot_ts=snapshot_ts)

    assert rows[0]["tickets_total"] == 1
    assert rows[0]["tickets_left"] == 1


def test_summarize_seat_payload_deduplicates_and_counts():
    payload = {
        "offers": {
            "full": {
                "seats": {
                    "X-1": {"seat_id": "X-1", "available": True},
                    "X-2": {"seat_id": "X-2", "available": False},
                }
            }
        },
        "zones": [
            {"seats": [{"seat_id": "X-1", "available": True}, {"seat_id": "X-3", "admission": True}]}
        ],
    }

    total, available = _summarize_seat_payload(payload)

    assert total == 3  # X-1 counted once despite duplication
    assert available == 2
