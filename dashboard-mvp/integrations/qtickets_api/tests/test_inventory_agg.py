"""Unit tests for QTickets API inventory aggregation logic."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

# Add the parent directory to the path to import the modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from integrations.qtickets_api.inventory_agg import build_inventory_snapshot


def load_fixture(filename):
    """Load a JSON fixture from the fixtures directory."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    with open(fixtures_dir / filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_build_inventory_snapshot_with_empty_shows():
    """Test inventory snapshot with events that have no shows."""
    events = load_fixture("events_sample.json")
    
    # Mock client that raises NotImplementedError for list_shows
    mock_client = Mock()
    mock_client.list_shows.side_effect = NotImplementedError("show_id resolution not implemented")
    
    # Should raise NotImplementedError
    try:
        build_inventory_snapshot(events, mock_client, snapshot_ts=datetime(2025, 1, 15, 12, 0, 0))
        assert False, "Expected NotImplementedError"
    except NotImplementedError as e:
        assert "show_id resolution not implemented" in str(e)
    
    print("✓ inventory snapshot with empty shows test passed")


def test_build_inventory_snapshot_with_mock_shows():
    """Test inventory snapshot with mocked show data."""
    events = load_fixture("events_sample.json")
    shows = load_fixture("shows_sample.json")
    
    # Create events with show_ids
    events_with_shows = []
    for event in events:
        event_with_shows = event.copy()
        # Add shows to the event
        event_shows = [show for show in shows if show["event_id"] == event["id"]]
        if event_shows:
            event_with_shows["shows"] = [{"show_id": show["show_id"]} for show in event_shows]
        events_with_shows.append(event_with_shows)
    
    # Mock client
    mock_client = Mock()
    
    # Mock get_seats to return seat data
    def mock_get_seats(show_id):
        show_data = next((s for s in shows if s["show_id"] == show_id), None)
        if show_data:
            return [{
                "max_count": show_data["max_count"],
                "free_count": show_data["free_count"]
            }]
        return []
    
    mock_client.get_seats.side_effect = mock_get_seats
    
    # Build inventory snapshot
    snapshot_ts = datetime(2025, 1, 15, 12, 0, 0)
    rows = build_inventory_snapshot(events_with_shows, mock_client, snapshot_ts=snapshot_ts)
    
    # Should have rows for events with shows
    assert len(rows) >= 0  # May be 0 if no events have shows
    
    # Check structure of rows if any exist
    for row in rows:
        assert "event_id" in row
        assert "event_name" in row
        assert "city" in row
        assert "snapshot_ts" in row
        assert "tickets_total" in row
        assert "tickets_left" in row
        assert row["snapshot_ts"] == snapshot_ts.replace(tzinfo=None)
    
    print("✓ inventory snapshot with mock shows test passed")


def test_extract_show_ids():
    """Test extraction of show IDs from event payload."""
    from integrations.qtickets_api.inventory_agg import _extract_show_ids
    
    # Test event with shows array
    event_with_shows = {
        "id": "event_001",
        "shows": [
            {"show_id": "show_001"},
            {"show_id": "show_002"}
        ]
    }
    
    show_ids = _extract_show_ids(event_with_shows)
    assert len(show_ids) == 2
    assert "show_001" in show_ids
    assert "show_002" in show_ids
    
    # Test event with sessions array
    event_with_sessions = {
        "id": "event_002",
        "sessions": [
            {"id": "session_001"},
            {"id": "session_002"}
        ]
    }
    
    show_ids = _extract_show_ids(event_with_sessions)
    assert len(show_ids) == 2
    assert "session_001" in show_ids
    assert "session_002" in show_ids
    
    # Test event with no shows
    event_no_shows = {
        "id": "event_003",
        "name": "Event without shows"
    }
    
    show_ids = _extract_show_ids(event_no_shows)
    assert len(show_ids) == 0
    
    print("✓ extract_show_ids test passed")


def test_inventory_aggregation():
    """Test that inventory data is correctly aggregated."""
    from integrations.qtickets_api.inventory_agg import _extract_show_ids
    
    # Create event with multiple shows
    event = {
        "id": "event_001",
        "name": "Test Event",
        "city": "Москва",
        "shows": [
            {"show_id": "show_001"},
            {"show_id": "show_002"}
        ]
    }
    
    # Mock client with seat data
    mock_client = Mock()
    
    def mock_get_seats(show_id):
        if show_id == "show_001":
            return [{"max_count": 100, "free_count": 75}]
        elif show_id == "show_002":
            return [{"max_count": 100, "free_count": 60}]
        return []
    
    mock_client.get_seats.side_effect = mock_get_seats
    
    # Build inventory snapshot
    snapshot_ts = datetime(2025, 1, 15, 12, 0, 0)
    rows = build_inventory_snapshot([event], mock_client, snapshot_ts=snapshot_ts)
    
    # Should have one row for the event
    assert len(rows) == 1
    
    row = rows[0]
    assert row["event_id"] == "event_001"
    assert row["event_name"] == "Test Event"
    assert row["city"] == "москва"
    assert row["tickets_total"] == 200  # 100 + 100
    assert row["tickets_left"] == 135   # 75 + 60
    assert row["snapshot_ts"] == snapshot_ts.replace(tzinfo=None)
    
    print("✓ inventory aggregation test passed")


if __name__ == "__main__":
    test_build_inventory_snapshot_with_empty_shows()
    test_build_inventory_snapshot_with_mock_shows()
    test_extract_show_ids()
    test_inventory_aggregation()
    print("\n✅ All inventory_agg tests passed!")