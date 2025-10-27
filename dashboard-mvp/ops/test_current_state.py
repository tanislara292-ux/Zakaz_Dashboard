#!/usr/bin/env python3
"""
Скрипт для проверки текущего состояния системы и тестирования подключений к ClickHouse
Использование: python3 ops/test_current_state.py [--verbose]
"""

import os
import sys
import json
import time
import argparse
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

# Добавляем корень проекта в путь
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def load_env(env_file='.env'):
    """Загрузка переменных окружения"""
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    return env_vars

def test_clickhouse_connection(host, port, database, username, password, use_https=True):
    """Тест подключения к ClickHouse"""
    print(f"Тест подключения к ClickHouse: {host}:{port}")
    
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{host}:{port}"
    
    try:
        # Тестовый запрос
        query = "SELECT 1 as test"
        full_url = f"{url}/?query={query}&user={username}&password={password}&database={database}"
        
        response = requests.get(full_url, timeout=10, verify=False)
        
        if response.status_code == 200:
            print("✅ Подключение к ClickHouse успешно")
            return True, "Подключение успешно установлено"
        else:
            print(f"❌ Ошибка подключения: HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL ошибка: {str(e)}")
        return False, f"SSL ошибка: {str(e)}"
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка соединения: {str(e)}")
        return False, f"Ошибка соединения: {str(e)}"
    except requests.exceptions.Timeout as e:
        print(f"❌ Таймаут: {str(e)}")
        return False, f"Таймаут: {str(e)}"
    except Exception as e:
        print(f"❌ Неизвестная ошибка: {str(e)}")
        return False, f"Неизвестная ошибка: {str(e)}"

def test_data_access(host, port, database, username, password, use_https=True):
    """Тест доступа к данным в ClickHouse"""
    print("\nТест доступа к данным:")
    
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{host}:{port}"
    
    tests = [
        {
            "name": "Проверка таблицы stg_qtickets_sales_raw",
            "query": "SELECT count() as cnt FROM zakaz.stg_qtickets_sales_raw"
        },
        {
            "name": "Проверка таблицы fact_vk_ads_daily",
            "query": "SELECT count() as cnt FROM zakaz.fact_vk_ads_daily"
        },
        {
            "name": "Проверка представления v_sales_latest",
            "query": "SELECT count() as cnt FROM zakaz.v_sales_latest"
        },
        {
            "name": "Проверка представления v_marketing_daily",
            "query": "SELECT count() as cnt FROM zakaz.v_marketing_daily"
        },
        {
            "name": "Проверка свежести данных продаж",
            "query": "SELECT max(event_date) as latest_date, today() - max(event_date) as days_behind FROM zakaz.v_sales_latest"
        },
        {
            "name": "Проверка свежести данных VK Ads",
            "query": "SELECT max(stat_date) as latest_date, today() - max(stat_date) as days_behind FROM zakaz.fact_vk_ads_daily"
        }
    ]
    
    results = []
    
    for test in tests:
        try:
            full_url = f"{url}/?query={test['query']}&user={username}&password={password}&database={database}"
            response = requests.get(full_url, timeout=10, verify=False)
            
            if response.status_code == 200:
                result = response.text.strip()
                print(f"✅ {test['name']}: {result}")
                results.append({"name": test['name'], "status": "ok", "result": result})
            else:
                print(f"❌ {test['name']}: HTTP {response.status_code}")
                results.append({"name": test['name'], "status": "error", "result": f"HTTP {response.status_code}"})
                
        except Exception as e:
            print(f"❌ {test['name']}: {str(e)}")
            results.append({"name": test['name'], "status": "error", "result": str(e)})
    
    return results

def test_docker_containers():
    """Тест работы Docker контейнеров"""
    print("\nТест Docker контейнеров:")
    
    try:
        # Проверка статуса контейнеров
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Docker работает:")
            print(result.stdout)
            
            # Проверка конкретных контейнеров
            containers = ['ch-zakaz', 'ch-zakaz-caddy']
            container_status = {}
            
            for container in containers:
                check_result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Status}}', container], 
                                            capture_output=True, text=True, timeout=5)
                if check_result.returncode == 0:
                    status = check_result.stdout.strip()
                    container_status[container] = status
                    if status == 'running':
                        print(f"✅ Контейнер {container}: {status}")
                    else:
                        print(f"❌ Контейнер {container}: {status}")
                else:
                    print(f"❌ Контейнер {container}: не найден")
                    container_status[container] = 'not_found'
            
            return container_status
        else:
            print("❌ Ошибка выполнения docker ps")
            return {}
            
    except subprocess.TimeoutExpired:
        print("❌ Таймаут выполнения docker команды")
        return {}
    except FileNotFoundError:
        print("❌ Docker не найден")
        return {}
    except Exception as e:
        print(f"❌ Ошибка проверки Docker: {str(e)}")
        return {}

def test_systemd_timers():
    """Тест работы systemd таймеров"""
    print("\nТест systemd таймеров:")
    
    try:
        # Проверка таймеров
        result = subprocess.run(['systemctl', 'list-timers', '--all'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Поиск релевантных таймеров
            relevant_timers = ['qtickets', 'vk_ads', 'direct', 'alerts', 'smoke_test_integrations']
            timer_lines = result.stdout.split('\n')
            
            found_timers = {}
            for line in timer_lines:
                for timer in relevant_timers:
                    if timer in line and 'TIMER' not in line:
                        found_timers[timer] = line.strip()
                        print(f"✅ Таймер {timer}: {line.strip()}")
                        break
            
            if not found_timers:
                print("⚠️ Релевантные таймеры не найдены")
            
            return found_timers
        else:
            print("❌ Ошибка выполнения systemctl list-timers")
            return {}
            
    except subprocess.TimeoutExpired:
        print("❌ Таймаут выполнения systemctl команды")
        return {}
    except Exception as e:
        print(f"❌ Ошибка проверки systemd таймеров: {str(e)}")
        return {}

def test_healthcheck():
    """Тест healthcheck сервера"""
    print("\nТест healthcheck сервера:")
    
    try:
        response = requests.get('http://localhost:8080/healthz', timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Healthcheck сервер работает: {response.text}")
            return True, response.text
        else:
            print(f"❌ Healthcheck сервер вернул: HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        print("❌ Healthcheck сервер недоступен")
        return False, "Сервер недоступен"
    except Exception as e:
        print(f"❌ Ошибка проверки healthcheck: {str(e)}")
        return False, str(e)

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Проверка текущего состояния системы')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    parser.add_argument('--env', type=str, default='.env', help='Путь к файлу окружения')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Проверка текущего состояния системы Zakaz Dashboard")
    print("=" * 50)
    
    # Загрузка переменных окружения
    env_vars = load_env(args.env)
    
    # Параметры подключения к ClickHouse
    host = env_vars.get('DOMAIN', 'bi.zakaz-dashboard.ru')
    port = 443
    database = 'zakaz'
    username = 'datalens_reader'
    password = env_vars.get('CLICKHOUSE_DATALENS_READER_PASSWORD', 'DataLens2024!Strong#Pass')
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': {}
    }
    
    # Тест 1: Docker контейнеры
    print("\n1. Проверка Docker контейнеров")
    print("-" * 30)
    container_status = test_docker_containers()
    results['tests']['docker_containers'] = container_status
    
    # Тест 2: Подключение к ClickHouse
    print("\n2. Проверка подключения к ClickHouse")
    print("-" * 30)
    ch_connected, ch_message = test_clickhouse_connection(host, port, database, username, password)
    results['tests']['clickhouse_connection'] = {
        'connected': ch_connected,
        'message': ch_message,
        'params': {
            'host': host,
            'port': port,
            'database': database,
            'username': username
        }
    }
    
    # Тест 3: Доступ к данным
    if ch_connected:
        print("\n3. Проверка доступа к данным")
        print("-" * 30)
        data_results = test_data_access(host, port, database, username, password)
        results['tests']['data_access'] = data_results
    
    # Тест 4: Systemd таймеры
    print("\n4. Проверка systemd таймеров")
    print("-" * 30)
    timer_results = test_systemd_timers()
    results['tests']['systemd_timers'] = timer_results
    
    # Тест 5: Healthcheck сервер
    print("\n5. Проверка healthcheck сервера")
    print("-" * 30)
    health_ok, health_message = test_healthcheck()
    results['tests']['healthcheck'] = {
        'working': health_ok,
        'message': health_message
    }
    
    # Итоги
    print("\n" + "=" * 50)
    print("ИТОГИ ПРОВЕРКИ")
    print("=" * 50)
    
    # Подсчет статусов
    total_tests = 5
    passed_tests = 0
    
    if container_status:
        running_containers = sum(1 for status in container_status.values() if status == 'running')
        if running_containers > 0:
            passed_tests += 1
            print(f"✅ Docker контейнеры: {running_containers} из {len(container_status)} работают")
        else:
            print(f"❌ Docker контейнеры: не работают")
    
    if ch_connected:
        passed_tests += 1
        print("✅ ClickHouse: подключение успешно")
    else:
        print("❌ ClickHouse: нет подключения")
    
    if ch_connected and 'data_access' in results['tests']:
        ok_data_tests = sum(1 for test in results['tests']['data_access'] if test['status'] == 'ok')
        total_data_tests = len(results['tests']['data_access'])
        if ok_data_tests > 0:
            passed_tests += 1
            print(f"✅ Доступ к данным: {ok_data_tests} из {total_data_tests} тестов пройдено")
        else:
            print("❌ Доступ к данным: тесты не пройдены")
    
    if timer_results:
        passed_tests += 1
        print(f"✅ Systemd таймеры: {len(timer_results)} найдено")
    else:
        print("❌ Systemd таймеры: не найдены")
    
    if health_ok:
        passed_tests += 1
        print("✅ Healthcheck сервер: работает")
    else:
        print("❌ Healthcheck сервер: не работает")
    
    print(f"\nОбщий результат: {passed_tests} из {total_tests} тестов пройдено")
    
    if passed_tests == total_tests:
        print("🎉 Система готова к настройке DataLens!")
    elif passed_tests >= 3:
        print("⚠️ Система частично готова, есть проблемы для решения")
    else:
        print("❌ Система не готова, требуются значительные доработки")
    
    # Сохранение результатов
    output_file = 'current_state_check.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\nДетальные результаты сохранены в: {output_file}")
    
    return 0 if passed_tests >= 3 else 1

if __name__ == '__main__':
    sys.exit(main())