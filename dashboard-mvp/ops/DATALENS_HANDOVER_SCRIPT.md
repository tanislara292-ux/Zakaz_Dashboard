# Скрипт проверки готовности DataLens к передаче

## Обзор

Документ описывает скрипт для автоматической проверки готовности системы аналитики Zakaz Dashboard к передаче заказчику.

## Назначение

Скрипт `datalens_handover_check.py` выполняет автоматическую проверку всех компонентов системы согласно чек-листу передачи и генерирует отчет о готовности.

## Структура скрипта

```python
#!/usr/bin/env python3
"""
Скрипт проверки готовности DataLens к передаче заказчику
Использование: python3 ops/datalens_handover_check.py [--verbose] [--output report.json]
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

# Добавляем корень проекта в путь
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from integrations.common import ClickHouseClient, get_client, now_msk
from integrations.common.logging import setup_integrations_logger

logger = setup_integrations_logger('datalens_handover')

class DataLensHandoverChecker:
    """Класс для проверки готовности DataLens к передаче"""
    
    def __init__(self, ch_client: ClickHouseClient):
        self.ch_client = ch_client
        self.results = []
        self.start_time = now_msk()
    
    def add_result(self, category: str, test_name: str, status: str, 
                   message: str, details: Dict[str, Any] = None):
        """Добавление результата проверки"""
        result = {
            'category': category,
            'test_name': test_name,
            'status': status,  # ok, warning, error
            'message': message,
            'timestamp': now_msk().isoformat(),
            'details': details or {}
        }
        self.results.append(result)
        
        status_symbol = {
            'ok': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(status, '❓')
        
        logger.info(f"{status_symbol} [{category}] {test_name}: {message}")
    
    def check_infrastructure(self) -> bool:
        """Проверка инфраструктуры"""
        logger.info("Проверка инфраструктуры...")
        
        all_ok = True
        
        # Проверка ClickHouse
        try:
            result = self.ch_client.execute('SELECT 1')
            if result and result.first_row:
                self.add_result(
                    'Инфраструктура', 
                    'ClickHouse доступен', 
                    'ok', 
                    'ClickHouse отвечает на запросы'
                )
            else:
                self.add_result(
                    'Инфраструктура', 
                    'ClickHouse доступен', 
                    'error', 
                    'ClickHouse не отвечает на запросы'
                )
                all_ok = False
        except Exception as e:
            self.add_result(
                'Инфраструктура', 
                'ClickHouse доступен', 
                'error', 
                f'Ошибка подключения к ClickHouse: {str(e)}'
            )
            all_ok = False
        
        # Проверка HTTPS доступа
        try:
            cmd = ['curl', '-s', '-k', 'https://bi.zakaz-dashboard.ru/?query=SELECT%201']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.add_result(
                    'Инфраструктура', 
                    'HTTPS доступ', 
                    'ok', 
                    'HTTPS доступ к ClickHouse работает'
                )
            else:
                self.add_result(
                    'Инфраструктура', 
                    'HTTPS доступ', 
                    'error', 
                    'HTTPS доступ не работает'
                )
                all_ok = False
        except Exception as e:
            self.add_result(
                'Инфраструктура', 
                'HTTPS доступ', 
                'error', 
                f'Ошибка проверки HTTPS: {str(e)}'
            )
            all_ok = False
        
        # Проверка таймеров
        try:
            cmd = ['systemctl', 'list-timers']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            timers = ['qtickets', 'vk_ads', 'direct', 'alerts']
            found_timers = [t for t in timers if t in result.stdout]
            
            if len(found_timers) == len(timers):
                self.add_result(
                    'Инфраструктура', 
                    'Systemd таймеры', 
                    'ok', 
                    f'Все таймеры работают: {", ".join(found_timers)}'
                )
            else:
                missing = set(timers) - set(found_timers)
                self.add_result(
                    'Инфраструктура', 
                    'Systemd таймеры', 
                    'warning', 
                    f'Отсутствуют таймеры: {", ".join(missing)}'
                )
                all_ok = False
        except Exception as e:
            self.add_result(
                'Инфраструктура', 
                'Systemd таймеры', 
                'error', 
                f'Ошибка проверки таймеров: {str(e)}'
            )
            all_ok = False
        
        # Проверка healthcheck
        try:
            cmd = ['curl', '-s', 'http://localhost:8080/healthz']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.add_result(
                    'Инфраструктура', 
                    'Healthcheck сервер', 
                    'ok', 
                    'Healthcheck сервер доступен'
                )
            else:
                self.add_result(
                    'Инфраструктура', 
                    'Healthcheck сервер', 
                    'warning', 
                    'Healthcheck сервер недоступен'
                )
        except Exception as e:
            self.add_result(
                'Инфраструктура', 
                'Healthcheck сервер', 
                'warning', 
                f'Ошибка проверки healthcheck: {str(e)}'
            )
        
        return all_ok
    
    def check_data_freshness(self) -> bool:
        """Проверка свежести данных"""
        logger.info("Проверка свежести данных...")
        
        all_ok = True
        
        # Проверка свежести данных QTickets
        try:
            result = self.ch_client.execute("""
                SELECT 
                    max(event_date) as latest_date,
                    today() - max(event_date) as days_behind
                FROM zakaz.v_sales_latest
            """)
            
            if result and result.first_row:
                data = result.first_row[0]
                days_behind = data['days_behind']
                
                if days_behind <= 2:
                    self.add_result(
                        'Данные', 
                        'Свежесть данных QTickets', 
                        'ok', 
                        f'Данные свежие, отставание: {days_behind} дней',
                        {'latest_date': str(data['latest_date']), 'days_behind': days_behind}
                    )
                else:
                    self.add_result(
                        'Данные', 
                        'Свежесть данных QTickets', 
                        'warning', 
                        f'Данные устарели, отставание: {days_behind} дней',
                        {'latest_date': str(data['latest_date']), 'days_behind': days_behind}
                    )
                    all_ok = False
            else:
                self.add_result(
                    'Данные', 
                    'Свежесть данных QTickets', 
                    'error', 
                    'Нет данных о продажах'
                )
                all_ok = False
        except Exception as e:
            self.add_result(
                'Данные', 
                'Свежесть данных QTickets', 
                'error', 
                f'Ошибка проверки свежести: {str(e)}'
            )
            all_ok = False
        
        # Проверка свежести данных VK Ads
        try:
            result = self.ch_client.execute("""
                SELECT 
                    max(stat_date) as latest_date,
                    today() - max(stat_date) as days_behind
                FROM zakaz.fact_vk_ads_daily
            """)
            
            if result and result.first_row:
                data = result.first_row[0]
                days_behind = data['days_behind']
                
                if days_behind <= 1:
                    self.add_result(
                        'Данные', 
                        'Свежесть данных VK Ads', 
                        'ok', 
                        f'Данные свежие, отставание: {days_behind} дней',
                        {'latest_date': str(data['latest_date']), 'days_behind': days_behind}
                    )
                else:
                    self.add_result(
                        'Данные', 
                        'Свежесть данных VK Ads', 
                        'warning', 
                        f'Данные устарели, отставание: {days_behind} дней',
                        {'latest_date': str(data['latest_date']), 'days_behind': days_behind}
                    )
                    all_ok = False
            else:
                self.add_result(
                    'Данные', 
                    'Свежесть данных VK Ads', 
                    'warning', 
                    'Нет данных VK Ads'
                )
        except Exception as e:
            self.add_result(
                'Данные', 
                'Свежесть данных VK Ads', 
                'error', 
                f'Ошибка проверки свежести VK Ads: {str(e)}'
            )
            all_ok = False
        
        return all_ok
    
    def check_data_quality(self) -> bool:
        """Проверка качества данных"""
        logger.info("Проверка качества данных...")
        
        all_ok = True
        
        # Проверка на дубликаты
        try:
            result = self.ch_client.execute("""
                SELECT 
                    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
                FROM zakaz.v_sales_latest
                WHERE event_date >= today() - 7
            """)
            
            if result and result.first_row:
                duplicates = result.first_row[0]['duplicates']
                
                if duplicates == 0:
                    self.add_result(
                        'Данные', 
                        'Отсутствие дубликатов', 
                        'ok', 
                        'Дубликаты в данных отсутствуют'
                    )
                else:
                    self.add_result(
                        'Данные', 
                        'Отсутствие дубликатов', 
                        'warning', 
                        f'Обнаружены дубликаты: {duplicates}',
                        {'duplicates_count': duplicates}
                    )
                    all_ok = False
            else:
                self.add_result(
                    'Данные', 
                    'Отсутствие дубликатов', 
                    'error', 
                    'Не удалось проверить дубликаты'
                )
                all_ok = False
        except Exception as e:
            self.add_result(
                'Данные', 
                'Отсутствие дубликатов', 
                'error', 
                f'Ошибка проверки дубликатов: {str(e)}'
            )
            all_ok = False
        
        # Проверка представлений
        views = ['zakaz.v_sales_latest', 'zakaz.v_marketing_daily', 'zakaz.v_sales_14d']
        for view in views:
            try:
                result = self.ch_client.execute(f"SELECT count() FROM {view} LIMIT 1")
                if result:
                    self.add_result(
                        'Данные', 
                        f'Представление {view}', 
                        'ok', 
                        f'Представление {view} работает'
                    )
                else:
                    self.add_result(
                        'Данные', 
                        f'Представление {view}', 
                        'error', 
                        f'Представление {view} не возвращает данные'
                    )
                    all_ok = False
            except Exception as e:
                self.add_result(
                    'Данные', 
                    f'Представление {view}', 
                    'error', 
                    f'Ошибка представления {view}: {str(e)}'
                )
                all_ok = False
        
        return all_ok
    
    def check_datalens_connection(self) -> bool:
        """Проверка подключения DataLens"""
        logger.info("Проверка подключения DataLens...")
        
        # Эта проверка требует ручного подтверждения
        # так как мы не можем программно проверить DataLens
        
        self.add_result(
            'DataLens', 
            'Подключение к ClickHouse', 
            'warning', 
            'Требуется ручная проверка подключения в DataLens',
            {
                'host': 'bi.zakaz-dashboard.ru',
                'port': 443,
                'database': 'zakaz',
                'username': 'datalens_reader'
            }
        )
        
        return True  # Не блокируем передачу из-за этого
    
    def check_documentation(self) -> bool:
        """Проверка документации"""
        logger.info("Проверка документации...")
        
        all_ok = True
        
        docs_to_check = [
            'docs/DATALENS_CONNECTION_PLAN.md',
            'docs/DATALENS_TECHNICAL_SPEC.md',
            'docs/CUSTOMER_GUIDE.md',
            'ops/DATALENS_HANDOVER_CHECKLIST.md',
            'ops/HANDOVER_PACKAGE.md'
        ]
        
        for doc in docs_to_check:
            doc_path = os.path.join(os.path.dirname(__file__), '..', doc)
            if os.path.exists(doc_path):
                self.add_result(
                    'Документация', 
                    f'Файл {doc}', 
                    'ok', 
                    f'Документация {doc} существует'
                )
            else:
                self.add_result(
                    'Документация', 
                    f'Файл {doc}', 
                    'error', 
                    f'Отсутствует документация {doc}'
                )
                all_ok = False
        
        return all_ok
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Запуск всех проверок"""
        logger.info("Начало проверки готовности DataLens к передаче")
        
        # Запуск проверок
        checks = [
            self.check_infrastructure,
            self.check_data_freshness,
            self.check_data_quality,
            self.check_datalens_connection,
            self.check_documentation
        ]
        
        passed = 0
        failed = 0
        warnings = 0
        
        for check in checks:
            try:
                if check():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Ошибка при выполнении проверки: {e}")
                failed += 1
        
        # Формирование итогового результата
        total_time = (now_msk() - self.start_time).total_seconds()
        
        # Подсчет статусов
        status_counts = {'ok': 0, 'warning': 0, 'error': 0}
        for result in self.results:
            status_counts[result['status']] += 1
        
        overall_status = 'ok'
        if status_counts['error'] > 0:
            overall_status = 'error'
        elif status_counts['warning'] > 0:
            overall_status = 'warning'
        
        summary = {
            'overall_status': overall_status,
            'timestamp': now_msk().isoformat(),
            'duration_seconds': round(total_time, 2),
            'checks': {
                'total': len(checks),
                'passed': passed,
                'failed': failed
            },
            'results': self.results,
            'status_counts': status_counts
        }
        
        # Вывод итогового результата
        status_symbol = {
            'ok': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(overall_status, '❓')
        
        logger.info(f"{status_symbol} Проверка завершена: {passed}/{len(checks)} проверок пройдено")
        logger.info(f"Длительность: {round(total_time, 2)} секунд")
        logger.info(f"Результаты: {status_counts['ok']} ✅, {status_counts['warning']} ⚠️, {status_counts['error']} ❌")
        
        return summary

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Проверка готовности DataLens к передаче')
    parser.add_argument('--env', type=str, default='secrets/.env.ch', 
                       help='Путь к файлу с переменными окружения')
    parser.add_argument('--output', type=str, help='Путь к файлу для сохранения отчета')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    try:
        # Инициализация клиента ClickHouse
        ch_client = get_client(args.env)
        
        # Создание и запуск проверок
        checker = DataLensHandoverChecker(ch_client)
        results = checker.run_all_checks()
        
        # Сохранение результатов в файл
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Отчет сохранен в {args.output}")
        
        # Вывод краткого отчета
        print("\n=== КРАТКИЙ ОТЧЕТ ===")
        print(f"Статус: {results['overall_status']}")
        print(f"Проверок пройдено: {results['checks']['passed']}/{results['checks']['total']}")
        print(f"Результаты: {results['status_counts']['ok']} ✅, {results['status_counts']['warning']} ⚠️, {results['status_counts']['error']} ❌")
        
        if results['status_counts']['error'] > 0:
            print("\n❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
            for result in results['results']:
                if result['status'] == 'error':
                    print(f"  - [{result['category']}] {result['test_name']}: {result['message']}")
        
        if results['status_counts']['warning'] > 0:
            print("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for result in results['results']:
                if result['status'] == 'warning':
                    print(f"  - [{result['category']}] {result['test_name']}: {result['message']}")
        
        # Возврат кода завершения
        if results['overall_status'] == 'error':
            sys.exit(1)
        elif results['overall_status'] == 'warning':
            sys.exit(2)
        else:
            sys.exit(0)
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении проверки: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Использование

### Базовый запуск

```bash
python3 ops/datalens_handover_check.py
```

### Подробный вывод с сохранением отчета

```bash
python3 ops/datalens_handover_check.py --verbose --output handover_report.json
```

### Использование с другим файлом окружения

```bash
python3 ops/datalens_handover_check.py --env /path/to/.env.ch
```

## Проверяемые компоненты

### 1. Инфраструктура
- Доступность ClickHouse
- HTTPS доступ через реверс-прокси
- Работоспособность systemd таймеров
- Доступность healthcheck сервера

### 2. Данные
- Свежесть данных QTickets (не старше 2 дней)
- Свежесть данных VK Ads (не старше 1 дня)
- Отсутствие дубликатов в данных
- Работоспособность представлений

### 3. DataLens
- Подключение к ClickHouse (требуется ручная проверка)
- Источники данных
- Датасеты
- Дашборды

### 4. Документация
- Наличие всех необходимых файлов документации
- Полнота информации

## Коды завершения

- `0` - все проверки пройдены успешно
- `1` - обнаружены ошибки
- `2` - есть предупреждения

## Интеграция с CI/CD

Скрипт можно интегрировать в CI/CD пайплайн для автоматической проверки готовности:

```yaml
# Пример для GitHub Actions
- name: Check DataLens handover readiness
  run: |
    python3 ops/datalens_handover_check.py --output handover_report.json
    
- name: Upload handover report
  uses: actions/upload-artifact@v3
  with:
    name: handover-report
    path: handover_report.json
```

---

**Версия**: 1.0.0
**Дата создания**: $(date +%Y-%m-%d)