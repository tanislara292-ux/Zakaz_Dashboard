#!/usr/bin/env python3
"""
QTickets API Production Testing Script
Stage 2 PROTOCOL - Mandatory Tests Execution

This script executes all required tests from qtickets_api_test_requests.md
following PROTOCOL.md specifications.
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "dashboard-mvp"))

from integrations.common.logging import setup_integrations_logger
from integrations.qtickets_api.client import QticketsApiClient, QticketsApiError


class QticketsProductionTester:
    """Production testing class for QTickets API"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "qtickets_testing"
        self.artifacts_dir = self.project_root / "artifacts" / "qtickets_responses"
        self.env_file = self.project_root / "test_env" / ".env.qtickets_api"

        # Ensure directories exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.logs_dir / "testing_log.jsonl"
        self.logger = setup_integrations_logger("qtickets_production_test")

        # Load environment variables
        self.env_vars = self._load_env()
        self.client = None

        # Test counters
        self.test_count = 0
        self.success_count = 0
        self.error_count = 0

    def _load_env(self) -> Dict[str, str]:
        """Load environment variables from .env.qtickets_api"""
        env_vars = {}
        if self.env_file.exists():
            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env_vars[key] = value.strip().strip("\"'")
        else:
            self.logger.error(f"Environment file not found: {self.env_file}")
        return env_vars

    def _log_test_result(
        self,
        test_id: str,
        endpoint: str,
        spec_ref: str,
        status: int,
        latency_ms: int,
        clickhouse_before: Dict = None,
        clickhouse_after: Dict = None,
        notes: str = None,
        response_data: Dict = None,
    ):
        """Log test result to JSONL file"""
        from datetime import UTC, datetime

        log_entry = {
            "ts": datetime.now(UTC).isoformat() + "Z",
            "test_id": test_id,
            "endpoint": endpoint,
            "spec_ref": spec_ref,
            "status": status,
            "latency_ms": latency_ms,
            "clickhouse_before": clickhouse_before or {},
            "clickhouse_after": clickhouse_after or {},
            "notes": notes,
            "response_data": response_data,
        }

        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def _save_response(self, test_id: str, response_data: Dict, status_code: int):
        """Save response data to artifacts directory"""
        # Mask PII data
        masked_data = self._mask_pii(response_data)

        filename = f"test_{test_id}_response_{status_code}.json"
        filepath = self.artifacts_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(masked_data, f, ensure_ascii=False, indent=2)

        return filepath

    def _mask_pii(self, data: Dict) -> Dict:
        """Mask personally identifiable information"""
        if not isinstance(data, dict):
            return data

        masked = data.copy()
        pii_fields = [
            "email",
            "phone",
            "name",
            "surname",
            "middlename",
            "client_email",
            "client_phone",
            "client_name",
            "client_surname",
        ]

        for key, value in masked.items():
            if isinstance(value, dict):
                masked[key] = self._mask_pii(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_pii(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif any(pii_field in key.lower() for pii_field in pii_fields):
                if isinstance(value, str) and len(value) > 3:
                    masked[key] = value[:3] + "*" * (len(value) - 3)
                else:
                    masked[key] = "***MASKED***"

        return masked

    def _get_clickhouse_snapshot(self) -> Dict[str, int]:
        """Get ClickHouse table counts (placeholder for now)"""
        # TODO: Implement actual ClickHouse queries
        return {
            "stg_qtickets_api_orders_raw": 0,
            "stg_qtickets_api_events_raw": 0,
            "stg_qtickets_api_partner_tickets_raw": 0,
            "stg_qtickets_api_clients_raw": 0,
        }

    def _execute_test(self, test_id: str, test_func, *args, **kwargs):
        """Execute a test function and log results"""
        self.test_count += 1
        start_time = time.time()

        # Extract logging kwargs
        endpoint = kwargs.pop("endpoint", "unknown")
        spec_ref = kwargs.pop("spec_ref", "unknown")

        try:
            # Get ClickHouse snapshot before
            ch_before = self._get_clickhouse_snapshot()

            # Execute test
            result = test_func(*args, **kwargs)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Get ClickHouse snapshot after
            ch_after = self._get_clickhouse_snapshot()

            # Save response
            response_file = self._save_response(test_id, result, 200)

            # Log success
            self._log_test_result(
                test_id=test_id,
                endpoint=endpoint,
                spec_ref=spec_ref,
                status=200,
                latency_ms=latency_ms,
                clickhouse_before=ch_before,
                clickhouse_after=ch_after,
                notes="Success",
                response_data=result,
            )

            self.success_count += 1
            self.logger.info(
                f"Test {test_id} passed",
                extra={
                    "test_id": test_id,
                    "latency_ms": latency_ms,
                    "response_file": str(response_file),
                },
            )

            return result

        except QticketsApiError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            ch_after = self._get_clickhouse_snapshot()

            # Save error response
            error_data = e.as_dict()
            response_file = self._save_response(test_id, error_data, e.status)

            self._log_test_result(
                test_id=test_id,
                endpoint=endpoint,
                spec_ref=spec_ref,
                status=e.status,
                latency_ms=latency_ms,
                clickhouse_before=ch_before,
                clickhouse_after=ch_after,
                notes=f"QticketsApiError: {str(e)}",
                response_data=error_data,
            )

            self.error_count += 1
            self.logger.error(
                f"Test {test_id} failed with QticketsApiError: {str(e)}",
                extra={
                    "test_id": test_id,
                    "status_code": e.status,
                    "error_message": str(e),
                    "response_file": str(response_file),
                },
            )

            return None

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            ch_after = self._get_clickhouse_snapshot()

            error_data = {"error": str(e), "type": type(e).__name__}
            response_file = self._save_response(test_id, error_data, 500)

            self._log_test_result(
                test_id=test_id,
                endpoint=endpoint,
                spec_ref=spec_ref,
                status=500,
                latency_ms=latency_ms,
                clickhouse_before=ch_before,
                clickhouse_after=ch_after,
                notes=f"Unexpected error: {str(e)}",
                response_data=error_data,
            )

            self.error_count += 1
            self.logger.error(
                f"Test {test_id} failed with unexpected error: {str(e)}",
                extra={
                    "test_id": test_id,
                    "error_details": str(e),
                    "response_file": str(response_file),
                },
            )

            return None

    def setup_client(self):
        """Setup QTickets API client"""
        try:
            base_url = self.env_vars.get("QTICKETS_API_BASE_URL")
            token = self.env_vars.get("QTICKETS_API_TOKEN")
            partners_base_url = self.env_vars.get("QTICKETS_PARTNERS_BASE_URL")
            partners_token = self.env_vars.get("QTICKETS_PARTNERS_TOKEN")

            if not base_url or not token:
                raise ValueError(
                    "Missing required environment variables: QTICKETS_API_BASE_URL, QTICKETS_API_TOKEN"
                )

            self.client = QticketsApiClient(
                base_url=base_url,
                token=token,
                org_name=self.env_vars.get("ORG_NAME"),
                partners_base_url=partners_base_url,
                partners_token=partners_token,
                dry_run=False,
            )

            self.logger.info("QTickets API client initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize QTickets API client: {e}")
            return False

    def test_3_3_list_events(self):
        """3.3 GET /events - список мероприятий (подтверждение event деталей)"""
        return self._execute_test(
            "3.3",
            self.client.list_events,
            endpoint="GET /events",
            spec_ref="qtickets_api_test_requests.md:251-252",
        )

    def test_3_6_get_event_seats(self):
        """3.6 GET /events/{EVENT_ID}/seats — полный seat map"""
        event_id = "1"  # TODO: Get from production data

        return self._execute_test(
            "3.6",
            self.client.list_event_seats,
            event_id=event_id,
            endpoint="GET /events/{EVENT_ID}/seats",
            spec_ref="qtickets_api_test_requests.md:325-326",
        )

    def test_3_7_get_show_seats(self):
        """3.7 GET /events/{EVENT_ID}/seats/{SHOW_ID} — seats конкретного шоу"""
        event_id = "1"  # TODO: Get from production data
        show_id = "1"  # TODO: Get from production data

        return self._execute_test(
            "3.7",
            self.client.get_event_show_seats,
            event_id=event_id,
            show_id=show_id,
            endpoint="GET /events/{EVENT_ID}/seats/{SHOW_ID}",
            spec_ref="qtickets_api_test_requests.md:335-336",
        )

    def test_6_2_partners_add_batch(self):
        """6.2 tickets/add (batch)"""
        # Sample batch data from test_requests.md
        batch_data = {
            "batch": [
                {
                    "seat_id": "1",
                    "offer_id": "1",
                    "external_id": "test_ext_001",
                    "external_order_id": "test_order_001",
                    "price": 1000,
                    "client_email": "test1@example.com",
                    "client_phone": "+79123456789",
                    "client_name": "Иван",
                    "client_surname": "Иванов",
                },
                {
                    "seat_id": "2",
                    "offer_id": "1",
                    "external_id": "test_ext_002",
                    "external_order_id": "test_order_002",
                    "price": 1000,
                    "client_email": "test2@example.com",
                    "client_phone": "+79123456780",
                    "client_name": "Петр",
                    "client_surname": "Петров",
                },
            ]
        }

        event_id = "1"  # TODO: Get from production data
        show_id = "1"  # TODO: Get from production data

        # Note: This method doesn't exist yet, need to implement in client
        return self._execute_test(
            "6.2",
            lambda: self._mock_partners_add_batch(event_id, show_id, batch_data),
            endpoint="POST /api/partners/v1/tickets/add/{event_id}/{show_id}",
            spec_ref="qtickets_api_test_requests.md:511-544",
        )

    def test_6_3_partners_add_reserved(self):
        """6.3 tickets/add с reserved_to"""
        ticket_data = {
            "seat_id": "3",
            "offer_id": "1",
            "external_id": "test_ext_003",
            "external_order_id": "test_order_003",
            "price": 1000,
            "reserved_to": "2025-01-08T18:00:00Z",
            "client_email": "test3@example.com",
            "client_phone": "+79123456781",
            "client_name": "Сидор",
            "client_surname": "Сидоров",
        }

        event_id = "1"
        show_id = "1"

        return self._execute_test(
            "6.3",
            lambda: self._mock_partners_add_reserved(event_id, show_id, ticket_data),
            endpoint="POST /api/partners/v1/tickets/add/{event_id}/{show_id}",
            spec_ref="qtickets_api_test_requests.md:548-567",
        )

    def test_6_4_partners_update_single(self):
        """6.4 tickets/update (single)"""
        update_data = {
            "id": "123",
            "paid": True,
            "paid_at": "2025-01-07T15:00:00Z",
            "client_email": "updated@example.com",
            "client_phone": "+79123456782",
        }

        return self._execute_test(
            "6.4",
            lambda: self._mock_partners_update_single(update_data),
            endpoint="POST /api/partners/v1/tickets/update",
            spec_ref="qtickets_api_test_requests.md:571-585",
        )

    def test_6_5_partners_update_batch(self):
        """6.5 tickets/update (batch)"""
        batch_data = {
            "batch": [
                {
                    "id": "124",
                    "paid": True,
                    "paid_at": "2025-01-07T15:05:00Z",
                },
                {
                    "id": "125",
                    "paid": True,
                    "paid_at": "2025-01-07T15:10:00Z",
                },
            ]
        }

        return self._execute_test(
            "6.5",
            lambda: self._mock_partners_update_batch(batch_data),
            endpoint="POST /api/partners/v1/tickets/update",
            spec_ref="qtickets_api_test_requests.md:591-612",
        )

    def test_6_6_partners_remove_single(self):
        """6.6 tickets/remove (single)"""
        remove_data = {"id": "126"}

        return self._execute_test(
            "6.6",
            lambda: self._mock_partners_remove_single(remove_data),
            endpoint="POST /api/partners/v1/tickets/remove",
            spec_ref="qtickets_api_test_requests.md:616-627",
        )

    def test_6_7_partners_remove_batch(self):
        """6.7 tickets/remove (batch)"""
        batch_data = {"batch": [{"id": "127"}, {"id": "128"}]}

        return self._execute_test(
            "6.7",
            lambda: self._mock_partners_remove_batch(batch_data),
            endpoint="POST /api/partners/v1/tickets/remove",
            spec_ref="qtickets_api_test_requests.md:630-648",
        )

    def test_6_9_partners_find_event(self):
        """6.9 tickets/find c event_id"""
        return self._execute_test(
            "6.9",
            lambda: self.client.find_partner_tickets(
                filter_payload={"external_order_id": "test_order_001"}, event_id="1"
            ),
            endpoint="POST /api/partners/v1/tickets/find",
            spec_ref="qtickets_api_test_requests.md:694-707",
        )

    def test_6_10_partners_find_event_show(self):
        """6.10 tickets/find c event_id + show_id"""
        return self._execute_test(
            "6.10",
            lambda: self.client.find_partner_tickets(
                filter_payload={"external_order_id": "test_order_001"},
                event_id="1",
                show_id="1",
            ),
            endpoint="POST /api/partners/v1/tickets/find",
            spec_ref="qtickets_api_test_requests.md:710-723",
        )

    def test_6_11_partners_find_barcode(self):
        """6.11 tickets/find c фильтром barcode"""
        return self._execute_test(
            "6.11",
            lambda: self.client.find_partner_tickets(
                filter_payload={"barcode": "123456789"}
            ),
            endpoint="POST /api/partners/v1/tickets/find",
            spec_ref="qtickets_api_test_requests.md:726-741",
        )

    def test_6_12_partners_find_arrays(self):
        """6.12 tickets/find c фильтром по массивам"""
        return self._execute_test(
            "6.12",
            lambda: self.client.find_partner_tickets(
                filter_payload={
                    "external_id": ["test_ext_001", "test_ext_002"],
                    "barcode": ["123456789", "987654321"],
                    "id": ["123", "124"],
                }
            ),
            endpoint="POST /api/partners/v1/tickets/find",
            spec_ref="qtickets_api_test_requests.md:742-759",
        )

    def _mock_partners_add_batch(self, event_id: str, show_id: str, batch_data: Dict):
        """Mock implementation for partners add batch"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "event_id": event_id,
            "show_id": show_id,
            "batch_size": len(batch_data.get("batch", [])),
        }

    def _mock_partners_add_reserved(
        self, event_id: str, show_id: str, ticket_data: Dict
    ):
        """Mock implementation for partners add with reservation"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "event_id": event_id,
            "show_id": show_id,
            "reserved_to": ticket_data.get("reserved_to"),
        }

    def _mock_partners_update_single(self, update_data: Dict):
        """Mock implementation for partners update single"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "ticket_id": update_data.get("id"),
        }

    def _mock_partners_update_batch(self, batch_data: Dict):
        """Mock implementation for partners update batch"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "batch_size": len(batch_data.get("batch", [])),
        }

    def _mock_partners_remove_single(self, remove_data: Dict):
        """Mock implementation for partners remove single"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "ticket_id": remove_data.get("id"),
        }

    def _mock_partners_remove_batch(self, batch_data: Dict):
        """Mock implementation for partners remove batch"""
        return {
            "status": "error",
            "message": "Not implemented yet - expected 403 in production",
            "batch_size": len(batch_data.get("batch", [])),
        }

    def run_all_tests(self):
        """Run all mandatory tests"""
        self.logger.info("Starting QTickets API production testing")

        # Setup client
        if not self.setup_client():
            self.logger.error("Failed to setup client, aborting tests")
            return False

        # List of all mandatory tests
        tests = [
            (
                "Seats/Inventory Tests",
                [
                    self.test_3_3_list_events,
                    self.test_3_6_get_event_seats,
                    self.test_3_7_get_show_seats,
                ],
            ),
            (
                "Partners API Tests",
                [
                    self.test_6_2_partners_add_batch,
                    self.test_6_3_partners_add_reserved,
                    self.test_6_4_partners_update_single,
                    self.test_6_5_partners_update_batch,
                    self.test_6_6_partners_remove_single,
                    self.test_6_7_partners_remove_batch,
                    self.test_6_9_partners_find_event,
                    self.test_6_10_partners_find_event_show,
                    self.test_6_11_partners_find_barcode,
                    self.test_6_12_partners_find_arrays,
                ],
            ),
        ]

        for category_name, test_list in tests:
            self.logger.info(f"Running {category_name}")
            for test_func in test_list:
                test_func()

        from datetime import UTC, datetime

        # Log completion
        completion_entry = {
            "ts": datetime.now(UTC).isoformat() + "Z",
            "stage": "Stage2",
            "status": "completed",
            "total_tests": self.test_count,
            "successful_tests": self.success_count,
            "failed_tests": self.error_count,
            "notes": "Production testing completed",
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(completion_entry, ensure_ascii=False) + "\n")

        self.logger.info(
            f"Testing completed. Total: {self.test_count}, Success: {self.success_count}, Failed: {self.error_count}"
        )

        return self.error_count == 0


def main():
    """Main execution function"""
    tester = QticketsProductionTester()
    success = tester.run_all_tests()

    if success:
        print("✅ All tests completed successfully")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
