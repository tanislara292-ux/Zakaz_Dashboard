#!/usr/bin/env python3
"""
Тестовый скрипт для QTickets Google Sheets интеграции.
Проверяет все компоненты интеграции.
"""

import os
import sys
import json
import argparse
from datetime import datetime, date
from typing import Dict, Any, List

# Добавляем корень проекта в путь для импорта модулей
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Тест импорта модулей."""
    print("🔍 Тестирование импортов...")
    
    try:
        from integrations.qtickets_sheets.gsheets_client import GoogleSheetsClient
        print("✅ gsheets_client импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта gsheets_client: {e}")
        return False
    
    try:
        from integrations.qtickets_sheets.transform import DataTransformer
        print("✅ transform импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта transform: {e}")
        return False
    
    try:
        from integrations.qtickets_sheets.upsert import ClickHouseUpsert
        print("✅ upsert импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта upsert: {e}")
        return False
    
    try:
        from integrations.qtickets_sheets.loader import QTicketsSheetsLoader
        print("✅ loader импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта loader: {e}")
        return False
    
    return True

def test_environment():
    """Тест переменных окружения."""
    print("\n🔍 Тестирование переменных окружения...")
    
    required_vars = [
        'GSERVICE_JSON',
        'SHEET_ID_SALES',
        'SHEET_ID_EVENTS',
        'SHEET_ID_INVENTORY',
        'TAB_SALES',
        'TAB_EVENTS',
        'TAB_INVENTORY'
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}={value[:20]}...")
        else:
            print(f"❌ Отсутствует {var}")
            all_ok = False
    
    return all_ok

def test_google_sheets_connection():
    """Тест подключения к Google Sheets."""
    print("\n🔍 Тестирование подключения к Google Sheets...")
    
    try:
        from integrations.qtickets_sheets.gsheets_client import GoogleSheetsClient
        
        client = GoogleSheetsClient()
        
        # Проверка информации о таблице продаж
        sheet_id = os.getenv('SHEET_ID_SALES')
        if sheet_id:
            info = client.get_sheet_info(sheet_id)
            if info:
                print(f"✅ Подключение к таблице продаж: {info.get('title', 'Unknown')}")
                print(f"   Листы: {[s['title'] for s in info.get('sheets', [])]}")
            else:
                print("❌ Не удалось получить информацию о таблице продаж")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Sheets: {e}")
        return False

def test_clickhouse_connection():
    """Тест подключения к ClickHouse."""
    print("\n🔍 Тестирование подключения к ClickHouse...")
    
    try:
        from integrations.common import get_client
        
        client = get_client('secrets/.env.ch')
        
        # Простая проверка
        result = client.execute('SELECT version()')
        if result and result.first_row:
            version = result.first_row[0]['version()']
            print(f"✅ Подключение к ClickHouse: {version}")
            return True
        else:
            print("❌ Не удалось получить версию ClickHouse")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка подключения к ClickHouse: {e}")
        return False

def test_tables_exist():
    """Тест существования таблиц."""
    print("\n🔍 Тестирование существования таблиц...")
    
    try:
        from integrations.common import get_client
        
        client = get_client('secrets/.env.ch')
        
        tables_to_check = [
            'zakaz.stg_qtickets_sheets_raw',
            'zakaz.stg_qtickets_sheets_events',
            'zakaz.stg_qtickets_sheets_inventory',
            'zakaz.stg_qtickets_sheets_sales',
            'zakaz.dim_events',
            'zakaz.fact_qtickets_inventory',
            'zakaz.fact_qtickets_sales'
        ]
        
        all_exist = True
        for table in tables_to_check:
            try:
                result = client.execute(f"EXISTS TABLE {table}")
                if result and result.first_row:
                    exists = result.first_row[0][f'EXISTS TABLE {table}']
                    if exists:
                        print(f"✅ Таблица {table} существует")
                    else:
                        print(f"❌ Таблица {table} не существует")
                        all_exist = False
                else:
                    print(f"❌ Не удалось проверить таблицу {table}")
                    all_exist = False
            except Exception as e:
                print(f"❌ Ошибка проверки таблицы {table}: {e}")
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"❌ Ошибка при проверке таблиц: {e}")
        return False

def test_data_transformation():
    """Тест трансформации данных."""
    print("\n🔍 Тестирование трансформации данных...")
    
    try:
        from integrations.qtickets_sheets.transform import DataTransformer
        
        transformer = DataTransformer()
        
        # Тестовые данные
        test_event = {
            'event_id': 'test-123',
            'event_name': ' Test Event ',
            'event_date': '24.10.2025',
            'city': ' MOSCOW ',
            'tickets_total': '100',
            'tickets_left': '50'
        }
        
        transformed = transformer.transform_event(test_event)
        if transformed:
            print("✅ Трансформация мероприятия работает")
            print(f"   event_id: {transformed['event_id']}")
            print(f"   event_name: {transformed['event_name']}")
            print(f"   event_date: {transformed['event_date']}")
            print(f"   city: {transformed['city']}")
        else:
            print("❌ Трансформация мероприятия не работает")
            return False
        
        test_sale = {
            'date': '2025-10-24',
            'event_id': 'test-123',
            'event_name': ' Test Event ',
            'city': ' MOSCOW ',
            'tickets_sold': '25',
            'revenue': '2500.50',
            'refunds': '100.00',
            'currency': 'RUB'
        }
        
        transformed = transformer.transform_sale(test_sale)
        if transformed:
            print("✅ Трансформация продажи работает")
            print(f"   date: {transformed['date']}")
            print(f"   tickets_sold: {transformed['tickets_sold']}")
            print(f"   revenue: {transformed['revenue']}")
        else:
            print("❌ Трансформация продажи не работает")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка трансформации данных: {e}")
        return False

def test_full_loader():
    """Тест полного загрузчика в dry-run режиме."""
    print("\n🔍 Тестирование полного загрузчика (dry-run)...")
    
    try:
        from integrations.qtickets_sheets.loader import QTicketsSheetsLoader
        from integrations.common import get_client
        from integrations.qtickets_sheets.gsheets_client import GoogleSheetsClient
        from integrations.qtickets_sheets.transform import DataTransformer
        from integrations.qtickets_sheets.upsert import ClickHouseUpsert
        
        # Инициализация компонентов
        ch_client = get_client('secrets/.env.ch')
        gsheets_client = GoogleSheetsClient()
        transformer = DataTransformer()
        upserter = ClickHouseUpsert(ch_client)
        
        loader = QTicketsSheetsLoader(ch_client, gsheets_client, transformer, upserter)
        
        # Запуск в dry-run режиме
        results = loader.load_all(dry_run=True)
        
        print("✅ Dry-run загрузчик работает")
        print(f"   Результаты: {results}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка dry-run загрузчика: {e}")
        return False

def run_smoke_tests():
    """Запуск smoke-тестов."""
    print("\n🔍 Запуск smoke-тестов...")
    
    try:
        from integrations.common import get_client
        
        client = get_client('secrets/.env.ch')
        
        # Базовые проверки
        checks = [
            ("Проверка продаж за последние 3 дня", 
             "SELECT count() FROM zakaz.fact_qtickets_sales WHERE date >= today() - 3"),
            
            ("Проверка уникальных мероприятий", 
             "SELECT uniqExact(event_id) FROM zakaz.dim_events"),
            
            ("Проверка свежести данных", 
             "SELECT max(_ver) FROM zakaz.stg_qtickets_sheets_raw WHERE _ingest_ts >= now() - INTERVAL 1 HOUR")
        ]
        
        all_ok = True
        for check_name, query in checks:
            try:
                result = client.execute(query)
                if result and result.first_row:
                    value = result.first_row[0]
                    if isinstance(value, dict):
                        value = list(value.values())[0]
                    print(f"✅ {check_name}: {value}")
                else:
                    print(f"❌ {check_name}: нет данных")
                    all_ok = False
            except Exception as e:
                print(f"❌ {check_name}: ошибка {e}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"❌ Ошибка smoke-тестов: {e}")
        return False

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='Тестирование QTickets Google Sheets интеграции')
    parser.add_argument('--envfile', type=str, default='secrets/.env.qtickets_sheets', 
                       help='Путь к файлу с переменными окружения')
    parser.add_argument('--ch-env', type=str, default='secrets/.env.ch', 
                       help='Путь к файлу с переменными окружения ClickHouse')
    parser.add_argument('--skip-integration', action='store_true', 
                       help='Пропустить тесты интеграции')
    parser.add_argument('--verbose', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.envfile)
    load_dotenv(args.ch_env)
    
    print("🚀 Начало тестирования QTickets Google Sheets интеграции")
    print("=" * 60)
    
    tests = [
        ("Импорты", test_imports),
        ("Переменные окружения", test_environment),
    ]
    
    if not args.skip_integration:
        tests.extend([
            ("Подключение к Google Sheets", test_google_sheets_connection),
            ("Подключение к ClickHouse", test_clickhouse_connection),
            ("Существование таблиц", test_tables_exist),
            ("Трансформация данных", test_data_transformation),
            ("Полный загрузчик", test_full_loader),
            ("Smoke-тесты", run_smoke_tests),
        ])
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте {test_name}: {e}")
            results.append((test_name, False))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 Итоги тестирования:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Интеграция готова к работе.")
        return 0
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте ошибки выше.")
        return 1

if __name__ == '__main__':
    sys.exit(main())