#!/usr/bin/env python3
"""
Тестовый скрипт для проверки развертывания ClickHouse и загрузки данных.
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "ch-python"))

def run_command(cmd, cwd=None, check=True):
    """Выполнение команды с обработкой результата."""
    print(f"Выполняю: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=check
        )
        if result.stdout:
            print(f"Вывод: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            print(f"Ошибка: {result.stderr.strip()}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Команда завершилась с ошибкой: {e}")
        return False

def test_docker_compose():
    """Тест запуска Docker Compose."""
    print("\n=== Тест 1: Запуск ClickHouse через Docker Compose ===")
    
    # Проверяем наличие .env файла
    env_file = project_root / ".env"
    if not env_file.exists():
        print("ОШИБКА: Файл .env не найден. Скопируйте .env.sample в .env и настройте переменные.")
        return False
    
    # Запуск Docker Compose
    infra_dir = project_root / "dashboard-mvp" / "infra" / "clickhouse"
    if not infra_dir.exists():
        print(f"ОШИБКА: Директория {infra_dir} не найдена")
        return False
    
    if not run_command("docker compose up -d", cwd=infra_dir):
        print("ОШИБКА: Не удалось запустить Docker Compose")
        return False
    
    # Ожидание запуска ClickHouse
    print("Ожидаю запуск ClickHouse (10 секунд)...")
    time.sleep(10)
    
    # Проверка работоспособности
    if not run_command('docker exec ch-zakaz clickhouse-client -q "SELECT version()"'):
        print("ОШИБКА: ClickHouse не отвечает")
        return False
    
    print("✅ ClickHouse успешно запущен")
    return True

def test_database_initialization():
    """Тест инициализации БД и таблиц."""
    print("\n=== Тест 2: Инициализация БД и таблиц ===")
    
    infra_dir = project_root / "dashboard-mvp" / "infra" / "clickhouse"
    env_file = project_root / ".env"
    
    # Читаем пароль админа из .env
    admin_password = None
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith('CLICKHOUSE_ADMIN_PASSWORD='):
                    admin_password = line.split('=', 1)[1].strip()
                    break
    
    if not admin_password:
        print("ОШИБКА: CLICKHOUSE_ADMIN_PASSWORD не найден в .env")
        return False
    
    # Выполнение init.sql
    cmd = f'docker exec -i ch-zakaz clickhouse-client --user=admin --password={admin_password} < init.sql'
    if not run_command(cmd, cwd=infra_dir):
        print("ОШИБКА: Не удалось выполнить init.sql")
        return False
    
    # Проверка создания таблиц
    if not run_command('docker exec ch-zakaz clickhouse-client -q "SHOW TABLES FROM zakaz"'):
        print("ОШИБКА: Не удалось проверить таблицы")
        return False
    
    print("✅ БД и таблицы успешно созданы")
    return True

def test_python_loader():
    """Тест Python лоадера."""
    print("\n=== Тест 3: Проверка Python лоадера ===")
    
    ch_python_dir = project_root / "dashboard-mvp" / "ch-python"
    
    # Проверка установки зависимостей
    if not run_command("pip install -r requirements.txt", cwd=ch_python_dir, check=False):
        print("ПРЕДУПРЕЖДЕНИЕ: Не удалось установить зависимости (могут быть уже установлены)")
    
    # Проверка импорта модулей
    try:
        from loader.sheets_to_ch import SheetsToClickHouseLoader
        print("✅ Модули лоадера успешно импортированы")
    except ImportError as e:
        print(f"ОШИБКА: Не удалось импортировать модули: {e}")
        return False
    
    # Проверка CLI (без реальной загрузки)
    cmd = "python cli.py --help"
    if not run_command(cmd, cwd=ch_python_dir):
        print("ОШИБКА: CLI не работает")
        return False
    
    print("✅ Python лоадер готов к работе")
    return True

def test_smoke_checks():
    """Тест smoke-проверок SQL."""
    print("\n=== Тест 4: Выполнение smoke-проверок ===")
    
    infra_dir = project_root / "dashboard-mvp" / "infra" / "clickhouse"
    
    # Выполнение smoke_checks.sql
    cmd = 'docker exec -i ch-zakaz clickhouse-client < smoke_checks.sql'
    if not run_command(cmd, cwd=infra_dir):
        print("ОШИБКА: Не удалось выполнить smoke-проверки")
        return False
    
    print("✅ Smoke-проверки выполнены успешно")
    return True

def main():
    """Основная функция тестирования."""
    print("🚀 Начинаю тестирование развертывания ClickHouse...")
    
    tests = [
        test_docker_compose,
        test_database_initialization,
        test_python_loader,
        test_smoke_checks,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ Тест {test.__name__} не пройден")
    
    print(f"\n=== Результаты тестирования ===")
    print(f"Пройдено: {passed}/{total} тестов")
    
    if passed == total:
        print("🎉 Все тесты пройдены! ClickHouse готов к использованию.")
        print("\nСледующие шаги:")
        print("1. Настройте GOOGLE_APPLICATION_CREDENTIALS и GOOGLE_SHEETS_SPREADSHEET_ID в .env")
        print("2. Запустите загрузку данных: cd dashboard-mvp/ch-python && python cli.py --days 7")
        print("3. Проверьте результаты: docker exec -i ch-zakaz clickhouse-client < infra/clickhouse/smoke_checks.sql")
        return True
    else:
        print("❌ Некоторые тесты не пройдены. Проверьте ошибки выше.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)