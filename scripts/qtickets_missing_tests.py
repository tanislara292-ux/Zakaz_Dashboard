#!/usr/bin/env python3
"""
Скрипт для выполнения недостающих тестов QTickets API и сбора артефактов
Отсутствующие тесты: 3.6, 3.7, 6.1, 6.8, 6.13, 6.14, 6.15
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("qtickets_missing_tests.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class QticketsMissingTests:
    def __init__(self):
        self.base_url = "https://qtickets.ru/api"
        self.token = "test_token_replacement"  # Будет загружен из env
        self.results_dir = Path(
            "D:/Projects/Zakaz_Dashboard/artifacts/stage2_mandatory_tests"
        )
        self.jsonl_log_path = Path(
            "D:/Projects/Zakaz_Dashboard/logs/stage2_missing_tests.jsonl"
        )

        # Убедимся, что директории существуют
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Загрузим переменные окружения
        self._load_env()

    def _load_env(self):
        """Загрузка переменных окружения"""
        env_files = [
            "D:/Projects/Zakaz_Dashboard/secrets/.env.qtickets_api.production",
            "D:/Projects/Zakaz_Dashboard/dashboard-mvp/test_env/.env.qtickets_api",
        ]

        for env_file in env_files:
            if Path(env_file).exists():
                logger.info(f"Loading env from {env_file}")
                with open(env_file) as f:
                    for line in f:
                        if line.strip() and not line.startswith("#"):
                            key, value = line.strip().split("=", 1)
                            os.environ[key] = value.strip('"')
                break

        self.token = os.getenv("QTICKETS_PARTNERS_TOKEN", "test_token_replacement")
        logger.info(f"Token loaded (first 5 chars): {self.token[:5]}...")

    def _make_request(self, method, url, **kwargs):
        """Выполнение HTTP запроса"""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = "application/json"

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    def _save_artifact(self, test_id, filename, response_data):
        """Сохранение артефакта"""
        filepath = self.results_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Artifact saved: {filepath}")

    def _log_test_result(
        self,
        test_id,
        endpoint,
        spec_ref,
        status,
        latency_ms,
        clickhouse_before=None,
        clickhouse_after=None,
        notes=None,
    ):
        """Логирование результата теста в JSONL"""
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "test_id": test_id,
            "endpoint": endpoint,
            "spec_ref": spec_ref,
            "status": status,
            "latency_ms": latency_ms,
            "clickhouse_before": clickhouse_before or {},
            "clickhouse_after": clickhouse_after or {},
            "notes": notes or "",
        }

        with open(self.jsonl_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        logger.info(f"Test {test_id} logged: status={status}")

    def test_3_6_get_event_seats(self):
        """3.6 GET /events/{EVENT_ID}/seats (полный seat map)"""
        logger.info("Running test 3.6: GET /events/{EVENT_ID}/seats")

        event_id = "33"  # Из существующих тестов
        url = f"{self.base_url}/rest/v1/events/{event_id}/seats"

        start_time = time.time()
        response = self._make_request("GET", url)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.content else None,
            }

            self._save_artifact("3_6", "test_3_6_get_event_seats.json", result_data)

            notes = ""
            if response.status_code == 404:
                notes = (
                    "Expected 404 - endpoint may not be available or event not found"
                )
            elif response.status_code == 403:
                notes = "Expected 403 - permission denied for test token"

            self._log_test_result(
                "3.6",
                f"GET /api/rest/v1/events/{event_id}/seats",
                "qtickets_api_test_requests.md:325-330",
                response.status_code,
                latency_ms,
                notes=notes,
            )
        else:
            logger.error("Failed to get response for test 3.6")

    def test_3_7_get_show_seats(self):
        """3.7 GET /events/{EVENT_ID}/seats/{SHOW_ID}"""
        logger.info("Running test 3.7: GET /events/{EVENT_ID}/seats/{SHOW_ID}")

        event_id = "33"
        show_id = "41"  # Из примера в документации
        url = f"{self.base_url}/rest/v1/events/{event_id}/seats/{show_id}"

        start_time = time.time()
        response = self._make_request("GET", url)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.content else None,
            }

            self._save_artifact("3_7", "test_3_7_get_show_seats.json", result_data)

            notes = ""
            if response.status_code == 404:
                notes = "Expected 404 - show may not exist or endpoint unavailable"
            elif response.status_code == 403:
                notes = "Expected 403 - permission denied for test token"

            self._log_test_result(
                "3.7",
                f"GET /api/rest/v1/events/{event_id}/seats/{show_id}",
                "qtickets_api_test_requests.md:335-340",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def test_6_1_partners_add_single(self):
        """6.1 tickets/add (single)"""
        logger.info(
            "Running test 6.1: POST /api/partners/v1/tickets/add/{event_id}/{show_id}"
        )

        event_id = "33"
        show_id = "41"
        url = f"{self.base_url}/partners/v1/tickets/add/{event_id}/{show_id}"

        body = {
            "seat_id": 1,
            "offer_id": 1,
            "external_id": f"test_ext_{int(time.time())}",
            "external_order_id": f"test_order_{int(time.time())}",
            "price": 1000,
            "client_email": "test@example.com",
            "client_phone": "+79999999999",
            "client_name": "Test",
            "client_surname": "User",
            "client_middlename": "Testovich",
        }

        start_time = time.time()
        response = self._make_request("POST", url, json=body)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "request_body": body,
                "body": response.json() if response.content else None,
            }

            self._save_artifact("6_1", "test_6_1_partners_add_single.json", result_data)

            notes = ""
            if response.status_code == 403:
                notes = "Expected PERMISSION_DENIED - test token"
            elif response.status_code == 404:
                notes = "Event/show not found or endpoint unavailable"

            self._log_test_result(
                "6.1",
                f"POST /api/partners/v1/tickets/add/{event_id}/{show_id}",
                "qtickets_api_test_requests.md:486-507",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def test_6_8_partners_check(self):
        """6.8 tickets/check"""
        logger.info("Running test 6.8: POST /api/partners/v1/tickets/check")

        url = f"{self.base_url}/partners/v1/tickets/check"

        body = {"batch": [{"seat_id": 1, "offer_id": 1}, {"seat_id": 2, "offer_id": 2}]}

        start_time = time.time()
        response = self._make_request("POST", url, json=body)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "request_body": body,
                "body": response.json() if response.content else None,
            }

            self._save_artifact("6_8", "test_6_8_partners_check.json", result_data)

            notes = ""
            if response.status_code == 403:
                notes = "Expected PERMISSION_DENIED - test token"
            elif response.status_code == 404:
                notes = "Endpoint may not exist"

            self._log_test_result(
                "6.8",
                "POST /api/partners/v1/tickets/check",
                "qtickets_api_test_requests.md:651-672",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def test_6_13_partners_find_multiple(self):
        """6.13 find с множественными фильтрами"""
        logger.info(
            "Running test 6.13: POST /api/partners/v1/tickets/find (multiple filters)"
        )

        url = f"{self.base_url}/partners/v1/tickets/find"

        body = {
            "filter": {
                "external_order_id": f"test_order_{int(time.time())}",
                "external_id": f"test_ext_{int(time.time())}",
                "barcode": "TEST123456",
                "id": 1,
            }
        }

        start_time = time.time()
        response = self._make_request("POST", url, json=body)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "request_body": body,
                "body": response.json() if response.content else None,
            }

            self._save_artifact(
                "6_13", "test_6_13_partners_find_multiple.json", result_data
            )

            notes = ""
            if response.status_code == 403:
                notes = "Expected PERMISSION_DENIED - test token"
            elif response.status_code == 404:
                notes = "Endpoint may not exist"

            self._log_test_result(
                "6.13",
                "POST /api/partners/v1/tickets/find",
                "qtickets_api_test_requests.md:742-755",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def test_6_14_partners_events_seats(self):
        """6.14 events/seats (partners, event-level)"""
        logger.info("Running test 6.14: GET /api/partners/v1/events/{event_id}/seats")

        event_id = "33"
        url = f"{self.base_url}/partners/v1/events/{event_id}/seats"

        start_time = time.time()
        response = self._make_request("GET", url)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.content else None,
            }

            self._save_artifact(
                "6_14", "test_6_14_partners_events_seats.json", result_data
            )

            notes = ""
            if response.status_code == 404:
                notes = "Expected 404 - endpoint may not exist"
            elif response.status_code == 403:
                notes = "Expected PERMISSION_DENIED - test token"

            self._log_test_result(
                "6.14",
                f"GET /api/partners/v1/events/{event_id}/seats",
                "qtickets_api_test_requests.md:761-762",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def test_6_15_partners_show_seats(self):
        """6.15 events/seats (partners, show-level)"""
        logger.info(
            "Running test 6.15: GET /api/partners/v1/events/{event_id}/seats/{show_id}"
        )

        event_id = "33"
        show_id = "41"
        url = f"{self.base_url}/partners/v1/events/{event_id}/seats/{show_id}"

        start_time = time.time()
        response = self._make_request("GET", url)
        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.content else None,
            }

            self._save_artifact(
                "6_15", "test_6_15_partners_show_seats.json", result_data
            )

            notes = ""
            if response.status_code == 404:
                notes = "Expected 404 - endpoint may not exist"
            elif response.status_code == 403:
                notes = "Expected PERMISSION_DENIED - test token"

            self._log_test_result(
                "6.15",
                f"GET /api/partners/v1/events/{event_id}/seats/{show_id}",
                "qtickets_api_test_requests.md:771-772",
                response.status_code,
                latency_ms,
                notes=notes,
            )

    def run_all_missing_tests(self):
        """Запуск всех недостающих тестов"""
        logger.info("Starting missing QTickets API tests")

        tests = [
            self.test_3_6_get_event_seats,
            self.test_3_7_get_show_seats,
            self.test_6_1_partners_add_single,
            self.test_6_8_partners_check,
            self.test_6_13_partners_find_multiple,
            self.test_6_14_partners_events_seats,
            self.test_6_15_partners_show_seats,
        ]

        for test in tests:
            try:
                test()
                time.sleep(0.5)  # Небольшая задержка между запросами
            except Exception as e:
                logger.error(f"Test {test.__name__} failed: {e}")

        logger.info("All missing tests completed")


def main():
    """Главная функция"""
    tester = QticketsMissingTests()
    tester.run_all_missing_tests()


if __name__ == "__main__":
    main()
