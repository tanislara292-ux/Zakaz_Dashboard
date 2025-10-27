#!/usr/bin/env python3
"""
Manual smoke test for QTickets API with production token.

This script performs direct HTTP calls to QTickets API endpoints
to verify accessibility and data structure without ClickHouse integration.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from dotenv import load_dotenv


class QticketsSmokeTester:
    """Manual API smoke tester for QTickets."""

    def __init__(self, env_file: str):
        """Initialize with environment configuration."""
        load_dotenv(env_file)

        self.base_url = (
            os.getenv("QTICKETS_BASE_URL")
            or os.getenv("QTICKETS_API_BASE_URL", "")
        ).rstrip("/")
        self.token = os.getenv("QTICKETS_TOKEN") or os.getenv("QTICKETS_API_TOKEN", "")
        self.vendor_code = os.getenv("ORG_NAME") or os.getenv(
            "QTICKETS_VENDOR_CODE", ""
        )

        if not self.base_url or not self.token:
            raise ValueError("Missing QTICKETS_BASE_URL or QTICKETS_TOKEN")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "QTickets-Smoke-Test/1.0",
            }
        )

        # Create logs directory
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        self.results = {}

    def _mask_personal_data(self, data: Any) -> Any:
        """Mask personal information in API responses."""
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if key.lower() in [
                    "email",
                    "phone",
                    "telephone",
                    "mobile",
                    "first_name",
                    "last_name",
                    "name",
                    "patronymic",
                    "fio",
                ]:
                    masked[key] = "***"
                elif key.lower() in ["customer", "buyer"] and isinstance(value, dict):
                    masked[key] = self._mask_personal_data(value)
                elif isinstance(value, (dict, list)):
                    masked[key] = self._mask_personal_data(value)
                else:
                    masked[key] = value
            return masked
        elif isinstance(data, list):
            return [
                self._mask_personal_data(item) for item in data[:2]
            ]  # Only first 2 items
        return data

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request and collect metrics."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        start_time = time.time()

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            elapsed_ms = int((time.time() - start_time) * 1000)

            result = {
                "url": url,
                "method": method,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "content_length": len(response.content),
                "headers": dict(response.headers),
                "success": response.status_code == 200,
            }

            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    raw_data = response.json()
                    result["data"] = raw_data
                    result["data_masked"] = self._mask_personal_data(raw_data)
                except ValueError:
                    result["error"] = "Invalid JSON response"
                    result["raw_content"] = response.text[:500]
            else:
                result["error"] = (
                    f"Non-JSON response: {response.headers.get('content-type', 'unknown')}"
                )
                result["raw_content"] = response.text[:500]

            return result

        except requests.RequestException as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "url": url,
                "method": method,
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "content_length": 0,
                "error": str(e),
                "success": False,
            }

    def test_events_endpoint(self) -> Dict[str, Any]:
        """Test GET /events endpoint."""
        print("Testing /events endpoint...")

        # Filter out deleted events
        params = {"where": json.dumps([{"column": "deleted_at", "operator": "null"}])}
        result = self._make_request("GET", "events", params=params)

        if result["success"] and "data" in result:
            data = result["data"]
            # Handle both direct array and wrapped response
            if isinstance(data, dict) and "data" in data:
                events_list = data["data"]
            elif isinstance(data, list):
                events_list = data
            else:
                events_list = []

            count = len(events_list)
            result["summary"] = f"events count: {count}"

            # Extract key fields from first event
            if count > 0 and isinstance(events_list, list):
                first_event = events_list[0]
                if isinstance(first_event, dict):
                    result["sample_fields"] = {
                        "id": first_event.get("id"),
                        "name": first_event.get("name"),
                        "city": first_event.get("city"),
                        "start_date": first_event.get("start_date"),
                        "venue": first_event.get("venue"),
                    }

        return result

    def test_orders_endpoint(self) -> Dict[str, Any]:
        """Test POST /orders endpoint for paid orders."""
        print("Testing /orders endpoint...")

        # Get orders for last 24 hours
        since_hours = int(os.getenv("QTICKETS_SINCE_HOURS", "24"))
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=since_hours)

        filters = [
            {"column": "payed", "value": 1},
            {"column": "payed_at", "operator": ">=", "value": start_time.isoformat()},
            {"column": "payed_at", "operator": "<", "value": end_time.isoformat()},
        ]

        result = self._make_request("POST", "orders", json={"where": filters})

        if result["success"] and "data" in result:
            data = result["data"]
            # Handle both direct array and wrapped response
            if isinstance(data, dict) and "data" in data:
                orders_list = data["data"]
            elif isinstance(data, list):
                orders_list = data
            else:
                orders_list = []

            count = len(orders_list)
            result["summary"] = f"paid orders count: {count}"

            # Calculate revenue from first few orders
            if count > 0 and isinstance(orders_list, list):
                sample_revenue = 0
                for order in orders_list[:5]:  # First 5 orders
                    if isinstance(order, dict) and "baskets" in order:
                        baskets = order["baskets"]
                        if isinstance(baskets, list):
                            for basket in baskets:
                                if isinstance(basket, dict) and "price" in basket:
                                    sample_revenue += float(basket.get("price", 0))

                result["sample_revenue"] = sample_revenue
                result["revenue_calculation"] = "sum of baskets[*].price"

        return result

    def test_inventory_endpoint(
        self, events_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Test inventory endpoint if show_id is available."""
        print("Testing inventory endpoint...")

        if not events_response or "data" not in events_response:
            return {
                "success": False,
                "error": "No events data available for inventory testing",
                "summary": "SKIP - no events data",
            }

        # Extract events list from response
        data = events_response["data"]
        if isinstance(data, dict) and "data" in data:
            events_list = data["data"]
        elif isinstance(data, list):
            events_list = data
        else:
            events_list = []

        if not events_list:
            return {
                "success": False,
                "error": "Empty events list",
                "summary": "SKIP - empty events",
            }

        # Try to find show_id from events
        show_id = None
        if events_list and len(events_list) > 0:
            for event in events_list[:5]:  # Check first 5 events
                if isinstance(event, dict):
                    # First try to get show_id from nested shows array
                    shows = event.get("shows", [])
                    if isinstance(shows, list) and len(shows) > 0:
                        first_show = shows[0]
                        if isinstance(first_show, dict):
                            show_id = first_show.get("id")
                            if show_id:
                                break

                    # Fallback to event-level IDs
                    if not show_id:
                        show_id = (
                            event.get("show_id")
                            or event.get("session_id")
                            or event.get("id")
                        )
                    if show_id:
                        break

        if not show_id:
            return {
                "success": False,
                "error": "No show_id found in events data",
                "summary": "SKIP - no show_id in events",
            }

        # Test seats endpoint
        endpoint = f"shows/{show_id}/seats"
        result = self._make_request("GET", endpoint)

        if result["success"] and "data" in result:
            data = result["data"]
            # Handle both direct array and wrapped response
            if isinstance(data, dict) and "data" in data:
                seats_list = data["data"]
            elif isinstance(data, list):
                seats_list = data
            else:
                seats_list = []

            count = len(seats_list)
            result["summary"] = f"seats count: {count}"

            # Extract inventory fields
            if count > 0 and isinstance(seats_list, list) and len(seats_list) > 0:
                first_seat = seats_list[0]
                if isinstance(first_seat, dict):
                    result["sample_fields"] = {
                        "max_count": first_seat.get("max_count"),
                        "free_count": first_seat.get("free_count"),
                        "payed_count": first_seat.get("payed_count"),
                        "reserved_count": first_seat.get("reserved_count"),
                    }

        return result

    def save_raw_response(self, filename: str, data: Any) -> None:
        """Save raw API response to file."""
        filepath = self.logs_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f"Saved raw response to {filepath}")

    def run_all_tests(self) -> None:
        """Run all smoke tests and generate report."""
        print("=" * 60)
        print("QTickets API Smoke Test - Starting")
        print(f"Base URL: {self.base_url}")
        print(f"Vendor Code: {self.vendor_code}")
        print("=" * 60)

        # Test events
        events_result = self.test_events_endpoint()
        self.results["events"] = events_result

        # Save raw events response
        if "data" in events_result:
            self.save_raw_response("qtickets_events_raw.json", events_result["data"])

        # Test orders
        orders_result = self.test_orders_endpoint()
        self.results["orders"] = orders_result

        # Save raw orders response
        if "data" in orders_result:
            self.save_raw_response("qtickets_orders_raw.json", orders_result["data"])

        # Test inventory
        inventory_result = self.test_inventory_endpoint(events_result)
        self.results["inventory"] = inventory_result

        # Save raw inventory response
        if "data" in inventory_result:
            self.save_raw_response(
                "qtickets_inventory_raw.json", inventory_result["data"]
            )

        # Print summary
        self.print_summary()

        # Save test results
        self.save_raw_response("qtickets_smoke_test_results.json", self.results)

    def print_summary(self) -> None:
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("QTickets API Smoke Test - Summary")
        print("=" * 60)

        for endpoint, result in self.results.items():
            status = "[OK]" if result.get("success", False) else "[FAIL]"
            status_code = result.get("status_code", "N/A")
            content_len = result.get("content_length", 0)
            summary = result.get("summary", "")

            print(
                f"{status} /{endpoint:<15} status={status_code} len={content_len:>6} bytes {summary}"
            )

        # Rate limit headers
        print("\nRate-limit headers:")
        for endpoint, result in self.results.items():
            headers = result.get("headers", {})
            rate_headers = {
                k: v
                for k, v in headers.items()
                if "rate" in k.lower() or "limit" in k.lower()
            }
            if rate_headers:
                print(f"  /{endpoint}: {rate_headers}")
            else:
                print(f"  /{endpoint}: no rate-limit headers")

        print("\n" + "=" * 60)

        # Overall assessment
        all_success = all(
            result.get("success", False) for result in self.results.values()
        )
        if all_success:
            print("✅ ALL TESTS PASSED - API is accessible and returning data")
        else:
            print("❌ SOME TESTS FAILED - Check individual results")

        print("=" * 60)


def main():
    """Main entry point."""
    env_file = "secrets/.env.qtickets_api.local"

    if not Path(env_file).exists():
        print(f"Error: Environment file not found: {env_file}")
        return 1

    try:
        tester = QticketsSmokeTester(env_file)
        tester.run_all_tests()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
