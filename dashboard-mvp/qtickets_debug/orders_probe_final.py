"""
Final QTickets Orders API Probe - Шаг 1 выполнен

Итоговое исследование блокера /orders с использованием правильного URL:
https://qtickets.ru/api/rest/v1

ОТВЕТ НА ОСНОВНОЙ ВОПРОС:
❌ НЕТ - мы не можем забирать заказы/выручку через /orders

Причина: эндпоинт /orders возвращает 503 Service Unavailable
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv


class OrdersFinalProbe:
    def __init__(self):
        """Инициализация с РАБОЧИМ URL из проекта"""
        # Правильный URL найден в manual_qtickets_smoke.py
        self.base_url = "https://qtickets.ru/api/rest/v1"
        self.token = None
        self.session = requests.Session()
        self.setup_auth()

    def setup_auth(self):
        """Загрузка токена"""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "secrets",
            ".env.qtickets_api.local",
        )

        load_dotenv(env_path)
        self.token = os.getenv("QTICKETS_API_TOKEN")

        if self.token:
            print(f"[TOKEN] Загружен: {self.token[:20]}...")
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        else:
            raise ValueError("QTICKETS_API_TOKEN не найден")

    def test_endpoint(self, method: str, endpoint: str, **kwargs):
        """Тестирование эндпоинта"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        print(f"\n{'=' * 60}")
        print(f"ЗАПРОС: {method} {url}")
        if kwargs.get("params"):
            print(f"Query: {kwargs['params']}")
        if kwargs.get("json"):
            print(f"Body: {json.dumps(kwargs['json'], indent=2)}")

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)

            print(f"СТАТУС: {response.status_code}")
            print(f"ЗАГОЛОВКИ: {dict(response.headers)}")

            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    data = response.json()
                    print(f"ТЕЛО (JSON): {json.dumps(data, indent=2)}")
                except:
                    pass
            else:
                print(f"ТЕЛО (TEXT): {response.text[:500]}...")

            return response.status_code, response.text

        except Exception as e:
            print(f"ОШИБКА: {e}")
            return 0, str(e)

    def test_working_endpoints(self):
        """Проверяем рабочие эндпоинты для сравнения"""
        print(f"\n{'#' * 60}")
        print("ПРОВЕРКА РАБОЧИХ ЭНДПОИНТОВ (для контроля)")
        print(f"{'#' * 60}")

        # /events - должен работать
        print(f"\n--- Тест /events (ожидается 200) ---")
        status, _ = self.test_endpoint("GET", "events")
        self.results["events"] = status

        # /inventory - должен работать
        print(f"\n--- Тест /inventory (ожидается 200) ---")
        status, _ = self.test_endpoint("GET", "inventory")
        self.results["inventory"] = status

    def test_orders_blocked(self):
        """Проверяем блокировку /orders разными способами"""
        print(f"\n{'#' * 60}")
        print("ПРОВЕРКА БЛОКИРОВКИ /orders")
        print(f"{'#' * 60}")

        # Способ 1: GET /orders (простой)
        print(f"\n--- Способ 1: GET /orders ---")
        status, _ = self.test_endpoint("GET", "orders")
        self.results["orders_get"] = status

        # Способ 2: GET /orders с параметрами
        print(f"\n--- Способ 2: GET /orders с параметрами ---")
        params = {
            "date_from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "date_to": datetime.now().strftime("%Y-%m-%d"),
            "limit": 10,
        }
        status, _ = self.test_endpoint("GET", "orders", params=params)
        self.results["orders_get_params"] = status

        # Способ 3: POST /orders с фильтрами (как в рабочем коде)
        print(f"\n--- Способ 3: POST /orders с фильтрами ---")
        filters = [
            {"column": "payed", "value": 1},
            {
                "column": "payed_at",
                "operator": ">=",
                "value": (datetime.now() - timedelta(hours=24)).isoformat(),
            },
            {
                "column": "payed_at",
                "operator": "<",
                "value": datetime.now().isoformat(),
            },
        ]
        status, _ = self.test_endpoint("POST", "orders", json={"where": filters})
        self.results["orders_post_filters"] = status

        # Способ 4: POST /orders с простым телом
        print(f"\n--- Способ 4: POST /orders с простым телом ---")
        payload = {
            "date_from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "date_to": datetime.now().strftime("%Y-%m-%d"),
            "limit": 10,
        }
        status, _ = self.test_endpoint("POST", "orders", json=payload)
        self.results["orders_post_simple"] = status

    def analyze_results(self):
        """Анализ результатов"""
        print(f"\n{'=' * 60}")
        print("ИТОГОВЫЙ АНАЛИЗ")
        print(f"{'=' * 60}")

        # Рабочие эндпоинты
        working_endpoints = []
        blocked_endpoints = []
        error_endpoints = []

        for endpoint, status in self.results.items():
            if status == 200:
                working_endpoints.append(endpoint)
                print(f"[WORKS] {endpoint}: 200 ✅")
            elif status == 503:
                blocked_endpoints.append(endpoint)
                print(f"[BLOCKED] {endpoint}: 503 ❌")
            else:
                error_endpoints.append(endpoint)
                print(f"[ERROR] {endpoint}: {status} ⚠️")

        print(f"\nСВОДКА:")
        print(f"- Рабочих эндпоинтов: {len(working_endpoints)}")
        print(f"- Заблокированных (503): {len(blocked_endpoints)}")
        print(f"- Другие ошибки: {len(error_endpoints)}")

        print(f"\nРАБОЧИЕ: {', '.join(working_endpoints)}")
        print(f"ЗАБЛОКИРОВАНЫ: {', '.join(blocked_endpoints)}")

        # Финальный вердикт по /orders
        orders_results = {k: v for k, v in self.results.items() if "orders" in k}

        if len(working_endpoints) > 0 and len(blocked_endpoints) == 0:
            print(f"\n[SUCCESS] API работает полностью")
            print("[ANSWER] ДА - мы можем забирать заказы через /orders")
            return True
        elif len(blocked_endpoints) > 0:
            print(f"\n[BLOCKED] /orders заблокирован")
            print(f"[DETAIL] Все попытки /orders возвращают 503")
            print("[ANSWER] НЕТ - мы не можем забирать заказы через /orders")
            return False
        else:
            print(f"\n[UNCLEAR] Неоднозначные результаты")
            print("[ANSWER] Нужен дополнительный анализ")
            return None

    def run_probe(self):
        """Основной метод пробы"""
        print(f"\n{'*' * 60}")
        print("ФИНАЛЬНАЯ ПРОБА QTICKETS /orders API")
        print(f"{'*' * 60}")
        print(f"Base URL: {self.base_url}")
        print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self.results = {}

        # Шаг 1: Проверяем рабочие эндпоинты
        self.test_working_endpoints()

        # Шаг 2: Проверяем блокировку /orders
        self.test_orders_blocked()

        # Шаг 3: Анализируем результаты
        result = self.analyze_results()

        # Шаг 4: Сохраняем отчет
        self.save_report(result)

        return result

    def save_report(self, final_result):
        """Сохранение отчета"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "question": "Мы можем забирать заказы/выручку через /orders?",
            "answer": "ДА"
            if final_result is True
            else "НЕТ"
            if final_result is False
            else "НЕЯСНО",
            "results": self.results,
            "summary": {
                "working_endpoints": len(
                    [s for s in self.results.values() if s == 200]
                ),
                "blocked_endpoints": len(
                    [s for s in self.results.values() if s == 503]
                ),
                "other_errors": len(
                    [s for s in self.results.values() if s not in [200, 503]]
                ),
            },
        }

        report_file = os.path.join(
            os.path.dirname(__file__), "orders_final_report.json"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[REPORT] Отчет сохранен: {report_file}")


if __name__ == "__main__":
    try:
        probe = OrdersFinalProbe()
        result = probe.run_probe()

        print(f"\n{'=' * 60}")
        print("ОКОНЧАТЕЛЬНЫЙ ОТВЕТ НА ВОПРОС ЗАДАЧИ:")
        print("Мы можем забирать заказы/выручку через /orders — да или нет?")
        print(
            f"ОТВЕТ: {'ДА' if result is True else 'НЕТ' if result is False else 'НЕЯСНО'}"
        )
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        sys.exit(1)
