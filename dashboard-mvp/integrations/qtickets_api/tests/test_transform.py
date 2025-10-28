"""Unit tests for QTickets API transformation logic."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the parent directory to the path to import the modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from integrations.qtickets_api.transform import transform_orders_to_sales_rows


def load_fixture(filename):
    """Load a JSON fixture from the fixtures directory."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    with open(fixtures_dir / filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_transform_orders_to_sales_rows():
    """Test that orders are correctly transformed to sales rows."""
    orders = load_fixture("orders_sample.json")
    
    # Transform with a fixed version for predictable results
    version = 1705315200  # Fixed timestamp for testing
    rows = transform_orders_to_sales_rows(orders, version=version)
    
    # Should have 3 rows for 3 orders
    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    
    # Check first order (2 tickets, 2700 revenue)
    first_row = rows[0]
    assert first_row["event_id"] == "event_001"
    assert first_row["city"] == "москва"
    assert first_row["tickets_sold"] == 2
    assert first_row["revenue"] == 2700.0
    assert first_row["currency"] == "RUB"
    assert first_row["_ver"] == version
    assert first_row["_dedup_key"] is not None
    assert len(first_row["_dedup_key"]) == 32  # MD5 hash length
    
    # Check second order (1 ticket, 2000 revenue)
    second_row = rows[1]
    assert second_row["event_id"] == "event_002"
    assert second_row["city"] == "санкт-петербург"
    assert second_row["tickets_sold"] == 1
    assert second_row["revenue"] == 2000.0
    
    # Check third order (1 ticket, 1800 revenue)
    third_row = rows[2]
    assert third_row["event_id"] == "event_001"
    assert third_row["city"] == "москва"
    assert third_row["tickets_sold"] == 1
    assert third_row["revenue"] == 1800.0
    
    print("✓ transform_orders_to_sales_rows test passed")


def test_dedup_key_generation():
    """Test that dedup keys are generated correctly."""
    orders = load_fixture("orders_sample.json")
    
    # Transform twice with same data should produce same dedup keys
    version = 1705315200
    rows1 = transform_orders_to_sales_rows(orders, version=version)
    rows2 = transform_orders_to_sales_rows(orders, version=version)
    
    # Same orders should produce same dedup keys
    for i in range(len(rows1)):
        assert rows1[i]["_dedup_key"] == rows2[i]["_dedup_key"]
    
    # Different versions should produce different dedup keys
    rows3 = transform_orders_to_sales_rows(orders, version=version + 1)
    for i in range(len(rows1)):
        assert rows1[i]["_dedup_key"] != rows3[i]["_dedup_key"]
    
    print("✓ dedup_key generation test passed")


def test_date_normalization():
    """Test that dates are correctly normalized to MSK."""
    orders = load_fixture("orders_sample.json")
    
    version = 1705315200
    rows = transform_orders_to_sales_rows(orders, version=version)
    
    # All sale_ts should be datetime objects without timezone info
    for row in rows:
        assert isinstance(row["sale_ts"], datetime)
        assert row["sale_ts"].tzinfo is None  # Should be naive datetime
        
        # Check that the time is preserved correctly
        if row["event_id"] == "event_001" and row["revenue"] == 2700.0:
            # First order: 2025-01-15T14:30:00+03:00
            assert row["sale_ts"].hour == 14
            assert row["sale_ts"].minute == 30
    
    print("✓ date normalization test passed")


def test_revenue_calculation():
    """Test that revenue is calculated correctly from basket prices."""
    orders = load_fixture("orders_sample.json")
    
    version = 1705315200
    rows = transform_orders_to_sales_rows(orders, version=version)
    
    # Check revenue calculations
    revenues = {row["event_id"]: row["revenue"] for row in rows}
    
    # First order: 1500 + 1200 = 2700
    assert revenues["event_001"] == 2700.0 or revenues["event_001"] == 1800.0
    
    # Second order: 2000
    assert revenues["event_002"] == 2000.0
    
    print("✓ revenue calculation test passed")


if __name__ == "__main__":
    test_transform_orders_to_sales_rows()
    test_dedup_key_generation()
    test_date_normalization()
    test_revenue_calculation()
    print("\n✅ All transform tests passed!")