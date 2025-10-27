"""
Simple QTickets Orders API Probe
Быстрая проверка доступности /orders на разных URL
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv


def test_orders_endpoint():
    # Загрузка токена
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "secrets",
        ".env.qtickets_api.local",
    )

    load_dotenv(env_path)
    token = os.getenv("QTICKETS_API_TOKEN")

    if not token:
        print("ERROR: Token not found")
        return False

    # Заголовки
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # URLs для теста
    urls = [
        "https://api.qtickets.app",
        "https://api.qtickets.ru/v1",
        "https://api.qtickets.com/v1",
    ]

    print("=== TESTING ROOT ENDPOINTS ===")

    # Сначала проверим корневые эндпоинты
    for url in urls:
        print(f"\nTesting root: {url}/")

        try:
            response = requests.get(
                f"{url}/", headers=headers, verify=False, timeout=10
            )

            print(f"Root response {url}: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(
                        f"Available paths: {list(data.keys()) if isinstance(data, dict) else 'Not JSON'}"
                    )
                except:
                    print(f"Response preview: {response.text[:200]}...")

        except Exception as e:
            print(f"Root error {url}: {str(e)}")

    print(f"\n=== TESTING /orders ENDPOINTS ===")

    results = {}

    for url in urls:
        print(f"\nTesting: {url}/orders")

        try:
            # Отключаем SSL проверку
            response = requests.get(
                f"{url}/orders", headers=headers, verify=False, timeout=10
            )

            status = response.status_code
            results[url] = status

            if status == 200:
                print(f"[SUCCESS] {url} - Status: {status}")
            elif status == 503:
                print(f"[503] {url} - Status: {503}")
            else:
                print(f"[ERROR] {url} - Status: {status}")

        except Exception as e:
            print(f"[EXCEPTION] {url} - Error: {str(e)}")
            results[url] = 0

    # Анализ результатов
    print(f"\n{'=' * 50}")
    print("FINAL ANALYSIS:")
    print(f"{'=' * 50}")

    success_count = sum(1 for status in results.values() if status == 200)
    error_503_count = sum(1 for status in results.values() if status == 503)

    print(f"Successful URLs: {success_count}")
    print(f"503 errors: {error_503_count}")

    for url, status in results.items():
        print(f"- {url}: {status}")

    if success_count > 0:
        print(f"\n[ANSWER] YES - we can get orders via /orders")
        return True
    elif error_503_count == len(urls):
        print(f"\n[ANSWER] NO - all URLs return 503")
        return False
    else:
        print(f"\n[ANSWER] UNCLEAR - mixed results")
        return None


if __name__ == "__main__":
    result = test_orders_endpoint()
    print(f"\nResult: {result}")
