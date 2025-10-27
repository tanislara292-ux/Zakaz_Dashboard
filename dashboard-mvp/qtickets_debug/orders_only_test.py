"""
Orders Only Test - финальная проверка блокера /orders
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta


def test_orders_only():
    # Загрузка токена
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "secrets",
        ".env.qtickets_api.local",
    )

    load_dotenv(env_path)
    token = os.getenv("QTICKETS_API_TOKEN")

    print(f"Token: {token[:20]}...")

    # Рабочий URL из проекта
    base_url = "https://qtickets.ru/api/rest/v1"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    results = {}

    print("\n=== TESTING ORDERS BLOCKER ===")

    # 1. GET /events (контроль - должен работать)
    print("\n1. GET /events (контроль)")
    try:
        resp = requests.get(f"{base_url}/events", headers=headers, timeout=10)
        results["events"] = resp.status_code
        print(
            f"   /events: {resp.status_code} {'✅' if resp.status_code == 200 else '❌'}"
        )
    except Exception as e:
        results["events"] = 0
        print(f"   /events: ERROR - {e}")

    # 2. GET /orders (проблемный)
    print("\n2. GET /orders")
    try:
        resp = requests.get(f"{base_url}/orders", headers=headers, timeout=10)
        results["orders_get"] = resp.status_code
        print(
            f"   GET /orders: {resp.status_code} {'✅' if resp.status_code == 200 else '❌' if resp.status_code == 503 else '⚠️'}"
        )
        if resp.status_code != 200:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        results["orders_get"] = 0
        print(f"   GET /orders: ERROR - {e}")

    # 3. GET /orders с параметрами (альтернатива POST)
    print("\n3. GET /orders с параметрами")
    params = {
        "date_from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date_to": datetime.now().strftime("%Y-%m-%d"),
        "limit": 10,
        "payed": 1,
    }

    try:
        resp = requests.get(
            f"{base_url}/orders", headers=headers, params=params, timeout=10
        )
        results["orders_get_params"] = resp.status_code
        print(
            f"   GET /orders с params: {resp.status_code} {'✅' if resp.status_code == 200 else '❌' if resp.status_code == 503 else '⚠️'}"
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    count = len(data["data"])
                    print(f"   Данные: {count} заказов получено")
                elif isinstance(data, list):
                    print(f"   Данные: {len(data)} заказов получено")
                else:
                    print(f"   Данные: ответ получен, структура неясна")
            except:
                print(f"   Данные: не JSON, но статус 200")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        results["orders_get_params"] = 0
        print(f"   GET /orders с params: ERROR - {e}")

    # 4. POST /orders с фильтрами (как в рабочем коде)
    print("\n4. POST /orders с фильтрами")
    filters = [
        {"column": "payed", "value": 1},
        {
            "column": "payed_at",
            "operator": ">=",
            "value": (datetime.now() - timedelta(hours=24)).isoformat(),
        },
        {"column": "payed_at", "operator": "<", "value": datetime.now().isoformat()},
    ]

    try:
        resp = requests.post(
            f"{base_url}/orders", headers=headers, json={"where": filters}, timeout=10
        )
        results["orders_post"] = resp.status_code
        print(
            f"   POST /orders: {resp.status_code} {'✅' if resp.status_code == 200 else '❌' if resp.status_code == 503 else '⚠️'}"
        )
        if resp.status_code != 200:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        results["orders_post"] = 0
        print(f"   POST /orders: ERROR - {e}")

    # Анализ
    print("\n=== ANALYSIS ===")

    events_works = results.get("events") == 200
    orders_blocked = all(
        status in [503, 0] for key, status in results.items() if "orders" in key
    )
    orders_work = all(
        status == 200 for key, status in results.items() if "orders" in key
    )

    # Проверяем, работает ли хотя бы один метод /orders
    orders_some_work = any(
        status == 200 for key, status in results.items() if "orders" in key
    )

    print(f"Events endpoint works: {events_works}")
    print(f"All /orders attempts failed with 503/errors: {orders_blocked}")
    print(f"All /orders attempts successful: {orders_work}")

    # Финальный ответ
    print("\n" + "=" * 60)
    print("ОТВЕТ НА ГЛАВНЫЙ ВОПРОС ЗАДАЧИ:")
    print("Мы можем забирать заказы/выручку через /orders — да или нет?")

    if events_works and orders_some_work:
        print("ОТВЕТ: ДА ✅")
        print(
            "ПРИЧИНА: Хотя бы один метод /orders работает (GET без параметров или с параметрами)"
        )
        print("РЕКОМЕНДАЦИЯ: Использовать рабочий GET метод для получения заказов")
        return True
    elif events_works and orders_blocked:
        print("ОТВЕТ: НЕТ ❌")
        print(
            "ПРИЧИНА: Все методы /orders заблокированы (503), другие эндпоинты работают"
        )
        print("РЕКОМЕНДАЦИЯ: Идти к вендору для разблокировки")
        return False
    else:
        print("ОТВЕТ: НЕЯСНО ❓")
        print("ПРИЧИНА: Смешанные результаты, нужно дополнительное исследование")
        return None


if __name__ == "__main__":
    result = test_orders_only()
    print(f"\nFinal result: {result}")
