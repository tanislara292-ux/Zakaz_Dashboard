"""
QTickets Orders API Probe
Шаг 1: Репродюс 503 ошибки на /orders в чистом виде

Скрипт выполняет 3 варианта запросов к /orders для определения характера проблемы:
- Вариант А: GET /orders без тела
- Вариант Б: GET /orders с query параметрами (dates)
- Вариант В: POST /orders с JSON телом
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Tuple

# Добавляем корень проекта в путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class OrdersProbe:
    def __init__(self):
        """Инициализация пробы с загрузкой токена из .env файла"""
        # Пробуем разные URL - сначала .app, потом .ru, потом .com
        self.base_urls = [
            "https://api.qtickets.app",
            "https://api.qtickets.ru/v1",
            "https://api.qtickets.com/v1",
        ]
        self.current_url_index = 0
        self.base_url = self.base_urls[self.current_url_index]
        self.token = None
        self.session = requests.Session()
        # Отключаем проверку SSL для тестов
        self.session.verify = False
        self.setup_auth()

    def setup_auth(self):
        """Загружаем токен из secrets/.env.qtickets_api.local"""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "secrets",
            ".env.qtickets_api.local",
        )

        print(f"Загрузка токена из: {env_path}")

        if os.path.exists(env_path):
            load_dotenv(env_path)
            self.token = os.getenv("QTICKETS_API_TOKEN")

            if self.token:
                print(f"+ Токен успешно загружен: {self.token[:20]}...")
                self.session.headers.update(
                    {
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                )
            else:
                raise ValueError("QTICKETS_API_TOKEN не найден в .env файле")
        else:
            raise FileNotFoundError(f".env файл не найден по пути: {env_path}")

    def make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Выполняет HTTP запрос и возвращает (status_code, response_data)

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: API эндпоинт
            **kwargs: доп. параметры для requests

        Returns:
            Tuple[статус код, данные ответа]
        """
        url = f"{self.base_url}{endpoint}"

        print(f"\n{'=' * 60}")
        print(f"ЗАПРОС: {method} {url}")
        if kwargs.get("params"):
            print(f"Query params: {kwargs['params']}")
        if kwargs.get("json"):
            print(f"JSON тело: {json.dumps(kwargs['json'], indent=2)}")

        try:
            # Игнорируем предупреждения о SSL
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = self.session.request(method, url, **kwargs)

            print(f"СТАТУС: {response.status_code}")
            print(f"ЗАГОЛОВКИ ОТВЕТА: {dict(response.headers)}")

            # Пытаемся распарсить JSON
            try:
                response_data = response.json()
                print(f"ТЕЛО ОТВЕТА (JSON): {json.dumps(response_data, indent=2)}")
            except:
                response_data = response.text
                print(f"ТЕЛО ОТВЕТА (TEXT): {response_data}")

            return response.status_code, response_data

        except requests.exceptions.RequestException as e:
            print(f"ОШИБКА ЗАПРОСА: {e}")
            return 0, {"error": str(e)}

    def variant_a_get_no_body(self):
        """Вариант А: GET /orders без тела"""
        print(f"\n{'#' * 60}")
        print("ВАРИАНТ А: GET /orders без тела")
        print(f"{'#' * 60}")

        status_code, response_data = self.make_request("GET", "/orders")

        print(f"\nРЕЗУЛЬТАТ ВАРИАНТА А:")
        print(f"Статус: {status_code}")

        if status_code == 503:
            print("⚠️  Получена 503 ошибка - Service Unavailable")
        elif status_code == 200:
            print("✅ Запрос успешен")
        else:
            print(f"❌ Неожиданный статус код: {status_code}")

        return status_code, response_data

    def variant_b_get_with_params(self):
        """Вариант Б: GET /orders с query параметрами"""
        print(f"\n{'#' * 60}")
        print("ВАРИАНТ Б: GET /orders с query параметрами")
        print(f"{'#' * 60}")

        # Берем последние 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        params = {
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
            "limit": 10,
        }

        status_code, response_data = self.make_request("GET", "/orders", params=params)

        print(f"\nРЕЗУЛЬТАТ ВАРИАНТА Б:")
        print(f"Статус: {status_code}")

        if status_code == 503:
            print("⚠️  Получена 503 ошибка - Service Unavailable")
        elif status_code == 200:
            print("✅ Запрос успешен")
        else:
            print(f"❌ Неожиданный статус код: {status_code}")

        return status_code, response_data

    def variant_c_post_with_body(self):
        """Вариант В: POST /orders с JSON телом"""
        print(f"\n{'#' * 60}")
        print("ВАРИАНТ В: POST /orders с JSON телом")
        print(f"{'#' * 60}")

        # Берем последние 7 дней для POST запроса
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        payload = {
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
            "limit": 10,
        }

        status_code, response_data = self.make_request("POST", "/orders", json=payload)

        print(f"\nРЕЗУЛЬТАТ ВАРИАНТА В:")
        print(f"Статус: {status_code}")

        if status_code == 503:
            print("⚠️  Получена 503 ошибка - Service Unavailable")
        elif status_code == 200:
            print("✅ Запрос успешен")
        else:
            print(f"❌ Неожиданный статус код: {status_code}")

        return status_code, response_data

    def run_probe(self):
        """Выполняет все варианты проб"""
        print(f"\n{'*' * 50}")
        print("НАЧАЛО ПРОБЫ QTICKETS /orders API")
        print(f"{'*' * 50}")
        print(f"Пробуем URLs: {', '.join(self.base_urls)}")
        print(f"Время выполнения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Собираем результаты всех вариантов
        results = {}
        all_results = {}

        # Пробуем каждый URL
        for url_index, test_url in enumerate(self.base_urls):
            print(f"\n{'-' * 50}")
            print(f"ТЕСТИРУЕМ URL #{url_index + 1}: {test_url}")
            print(f"{'-' * 50}")

            self.base_url = test_url
            url_results = {}

            # Вариант А
            url_results["variant_a"] = self.variant_a_get_no_body()

            # Вариант Б
            url_results["variant_b"] = self.variant_b_get_with_params()

            # Вариант В
            url_results["variant_c"] = self.variant_c_post_with_body()

            all_results[f"url_{url_index + 1}"] = {
                "url": test_url,
                "results": url_results,
            }

        results = all_results

        # Итоговый анализ
        print(f"\n{'=' * 50}")
        print("ИТОГОВЫЙ АНАЛИЗ ПРОБЫ")
        print(f"{'=' * 50}")

        success_count = 0
        error_503_count = 0
        other_errors_count = 0
        successful_urls = []

        for url_key, url_data in results.items():
            url = url_data["url"]
            print(f"\n{'=' * 10} АНАЛИЗ URL: {url} {'=' * 10}")

            url_success = 0
            url_503 = 0
            url_other = 0

            for variant, (status, _) in url_data["results"].items():
                if status == 200:
                    url_success += 1
                    success_count += 1
                    print(f"[OK] {variant}: Статус {status} - Успех")
                elif status == 503:
                    url_503 += 1
                    error_503_count += 1
                    print(f"[503] {variant}: Статус {status} - Service Unavailable")
                else:
                    url_other += 1
                    other_errors_count += 1
                    print(f"[ERR] {variant}: Статус {status} - Другая ошибка")

            # Сводка по URL
            if url_success > 0:
                successful_urls.append(url)
                print(f"[WORKS] URL {url} - РАБОТАЕТ ({url_success} успешных запросов)")
            elif url_503 == 3:
                print(f"[BLOCKED] URL {url} - 503 на всех запросах")
            else:
                print(f"[UNSTABLE] URL {url} - Нестабилен ({url_other} ошибок)")

        print(f"\nСТАТИСТИКА:")
        print(f"- Успешных запросов: {success_count}")
        print(f"- 503 ошибок: {error_503_count}")
        print(f"- Других ошибок: {other_errors_count}")

        # Финальный вердикт
        if len(successful_urls) > 0:
            print(f"\n[SUCCESS] ВЕРДИКТ: /orders ДОСТУПЕН")
            print(f"[WORKING] Рабочие URLs: {', '.join(successful_urls)}")
            print(
                "[ANSWER] Ответ на основной вопрос: ДА, мы можем забирать заказы/выручку через /orders"
            )
        elif error_503_count >= 6:  # 3 URL × 3 запроса = 9 максимум
            print(
                f"\n[BLOCKED] ВЕРДИКТ: /orders ЗАБЛОКИРОВАН (все запросы возвращают 503)"
            )
            print(
                "[ANSWER] Ответ на основной вопрос: НЕТ, мы не можем забирать заказы/выручку через /orders"
            )
        else:
            print(f"\n[UNCLEAR] ВЕРДИКТ: /orders НЕСТАБИЛЕН (смешанные результаты)")
            print("[ANSWER] Ответ на основной вопрос: Нужен дополнительный анализ")
            print(
                f"[STATS] Статистика: {success_count} успехов, {error_503_count} ошибок 503, {other_errors_count} других ошибок"
            )

        return results


if __name__ == "__main__":
    try:
        probe = OrdersProbe()
        results = probe.run_probe()

        # Сохраняем результаты в лог-файл
        log_file = os.path.join(os.path.dirname(__file__), "orders_probe_log.json")

        # Преобразуем результаты для лога
        log_results = {}
        for url_key, url_data in results.items():
            log_results[url_key] = {
                "url": url_data["url"],
                "variant_a": {"status_code": url_data["results"]["variant_a"][0]},
                "variant_b": {"status_code": url_data["results"]["variant_b"][0]},
                "variant_c": {"status_code": url_data["results"]["variant_c"][0]},
            }

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "urls_tested": self.base_urls,
            "results": log_results,
        }

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        print(f"\n[LOG] Лог сохранен в: {log_file}")

    except Exception as e:
        print(f"\n[ERROR] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)
