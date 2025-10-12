"""
Smoke-тестирование системы интеграций.
Проверяет работоспособность всех компонентов системы.
"""

import os
import sys
import argparse
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, setup_integrations_logger
)

# Настройка логгера
logger = setup_integrations_logger('smoke_test')

class SmokeTester:
    """Класс для smoke-тестирования системы интеграций."""
    
    def __init__(self, ch_client: ClickHouseClient):
        """
        Инициализация smoke-тестера.
        
        Args:
            ch_client: клиент ClickHouse
        """
        self.ch_client = ch_client
        self.results = []
        self.start_time = now_msk()
    
    def add_result(self, test_name: str, status: str, message: str, 
                  details: Dict[str, Any] = None, duration: float = None):
        """
        Добавление результата теста.
        
        Args:
            test_name: название теста
            status: статус (ok, warning, error)
            message: сообщение
            details: детали
            duration: длительность в секундах
        """
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'timestamp': now_msk().isoformat(),
            'details': details or {}
        }
        
        if duration is not None:
            result['duration'] = duration
        
        self.results.append(result)
        
        # Вывод в лог
        status_symbol = {
            'ok': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(status, '❓')
        
        logger.info(f"{status_symbol} {test_name}: {message}")
        
        if details:
            for key, value in details.items():
                logger.info(f"  {key}: {value}")
    
    def test_clickhouse_connection(self) -> bool:
        """Тест подключения к ClickHouse."""
        test_name = "ClickHouse Connection"
        start_time = time.time()
        
        try:
            result = self.ch_client.execute('SELECT 1')
            
            if result and result.first_row:
                self.add_result(
                    test_name, 'ok', 'ClickHouse доступен',
                    {'result': result.first_row[0]},
                    time.time() - start_time
                )
                return True
            else:
                self.add_result(
                    test_name, 'error', 'ClickHouse вернул пустой результат',
                    duration=time.time() - start_time
                )
                return False
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка подключения к ClickHouse: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def test_tables_exist(self) -> bool:
        """Тест наличия необходимых таблиц."""
        test_name = "Tables Existence"
        start_time = time.time()
        
        required_tables = [
            'zakaz.stg_qtickets_sales_raw',
            'zakaz.dim_events',
            'zakaz.fact_vk_ads_daily',
            'zakaz.fact_direct_daily',
            'zakaz.v_sales_latest',
            'zakaz.v_marketing_daily',
            'zakaz.meta_job_runs',
            'zakaz.alerts'
        ]
        
        missing_tables = []
        existing_tables = []
        
        for table in required_tables:
            try:
                result = self.ch_client.execute(f"EXISTS TABLE {table}")
                if result and result.first_row and result.first_row[0]:
                    existing_tables.append(table)
                else:
                    missing_tables.append(table)
            except Exception as e:
                missing_tables.append(f"{table} (ошибка: {str(e)})")
        
        if not missing_tables:
            self.add_result(
                test_name, 'ok', 'Все необходимые таблицы существуют',
                {'tables_count': len(existing_tables), 'tables': existing_tables},
                time.time() - start_time
            )
            return True
        else:
            self.add_result(
                test_name, 'error', f'Отсутствуют таблицы: {", ".join(missing_tables)}',
                {'existing_tables': existing_tables, 'missing_tables': missing_tables},
                time.time() - start_time
            )
            return False
    
    def test_views_exist(self) -> bool:
        """Тест наличия необходимых представлений."""
        test_name = "Views Existence"
        start_time = time.time()
        
        required_views = [
            'zakaz.v_sales_latest',
            'zakaz.v_marketing_daily',
            'zakaz.v_data_freshness',
            'zakaz.v_romi_kpi'
        ]
        
        missing_views = []
        existing_views = []
        
        for view in required_views:
            try:
                result = self.ch_client.execute(f"SELECT count() FROM {view} LIMIT 1")
                if result:
                    existing_views.append(view)
                else:
                    missing_views.append(view)
            except Exception as e:
                missing_views.append(f"{view} (ошибка: {str(e)})")
        
        if not missing_views:
            self.add_result(
                test_name, 'ok', 'Все необходимые представления существуют',
                {'views_count': len(existing_views), 'views': existing_views},
                time.time() - start_time
            )
            return True
        else:
            self.add_result(
                test_name, 'error', f'Отсутствуют представления: {", ".join(missing_views)}',
                {'existing_views': existing_views, 'missing_views': missing_views},
                time.time() - start_time
            )
            return False
    
    def test_data_freshness(self) -> bool:
        """Тест свежести данных."""
        test_name = "Data Freshness"
        start_time = time.time()
        
        try:
            result = self.ch_client.execute("""
                SELECT 
                    source,
                    latest_date,
                    days_behind,
                    total_rows
                FROM zakaz.v_data_freshness
                ORDER BY days_behind DESC
            """)
            
            if not result or not result.first_row:
                self.add_result(
                    test_name, 'error', 'Нет данных о свежести',
                    duration=time.time() - start_time
                )
                return False
            
            freshness_data = result.first_row
            stale_sources = [row for row in freshness_data if row['days_behind'] > 2]
            
            if stale_sources:
                self.add_result(
                    test_name, 'warning', 
                    f'Устаревшие данные для {len(stale_sources)} источников',
                    {
                        'sources': freshness_data,
                        'stale_sources': stale_sources
                    },
                    time.time() - start_time
                )
                return False
            else:
                self.add_result(
                    test_name, 'ok', 'Данные свежие',
                    {
                        'sources': freshness_data,
                        'latest_date': freshness_data[0]['latest_date'] if freshness_data else None
                    },
                    time.time() - start_time
                )
                return True
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка проверки свежести данных: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def test_job_runs(self) -> bool:
        """Тест запусков задач."""
        test_name = "Job Runs"
        start_time = time.time()
        
        try:
            # Проверяем запуски за последние 24 часа
            result = self.ch_client.execute("""
                SELECT 
                    job,
                    status,
                    count() as runs,
                    max(started_at) as last_run,
                    avg(rows_processed) as avg_rows
                FROM zakaz.meta_job_runs
                WHERE started_at >= now() - INTERVAL 1 DAY
                GROUP BY job, status
                ORDER BY job, status
            """)
            
            if not result or not result.first_row:
                self.add_result(
                    test_name, 'warning', 'Нет запусков задач за последние 24 часа',
                    duration=time.time() - start_time
                )
                return False
            
            runs_data = result.first_row
            
            # Проверяем наличие успешных запусков
            successful_runs = [row for row in runs_data if row['status'] == 'success']
            failed_runs = [row for row in runs_data if row['status'] == 'error']
            
            if failed_runs:
                self.add_result(
                    test_name, 'warning', 
                    f'Есть неудачные запуски: {len(failed_runs)}',
                    {
                        'runs': runs_data,
                        'successful_runs': len(successful_runs),
                        'failed_runs': len(failed_runs)
                    },
                    time.time() - start_time
                )
                return False
            elif not successful_runs:
                self.add_result(
                    test_name, 'error', 'Нет успешных запусков за последние 24 часа',
                    {'runs': runs_data},
                    time.time() - start_time
                )
                return False
            else:
                self.add_result(
                    test_name, 'ok', 'Запуски задач работают нормально',
                    {
                        'runs': runs_data,
                        'successful_runs': len(successful_runs),
                        'failed_runs': len(failed_runs)
                    },
                    time.time() - start_time
                )
                return True
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка проверки запусков задач: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def test_alerts(self) -> bool:
        """Тест системы алертов."""
        test_name = "Alerts System"
        start_time = time.time()
        
        try:
            # Проверяем алерты за последние 24 часа
            result = self.ch_client.execute("""
                SELECT 
                    alert_type,
                    count() as alerts_count,
                    max(created_at) as last_alert
                FROM zakaz.alerts
                WHERE created_at >= now() - INTERVAL 1 DAY
                GROUP BY alert_type
                ORDER BY alert_type
            """)
            
            if not result or not result.first_row:
                self.add_result(
                    test_name, 'ok', 'Нет алертов за последние 24 часа',
                    duration=time.time() - start_time
                )
                return True
            
            alerts_data = result.first_row
            
            # Проверяем наличие критичных алертов
            critical_alerts = [row for row in alerts_data if row['alert_type'] == 'error']
            
            if critical_alerts:
                self.add_result(
                    test_name, 'warning', 
                    f'Есть критические алерты: {len(critical_alerts)}',
                    {
                        'alerts': alerts_data,
                        'critical_alerts': len(critical_alerts)
                    },
                    time.time() - start_time
                )
                return False
            else:
                self.add_result(
                    test_name, 'ok', 'Система алертов работает нормально',
                    {
                        'alerts': alerts_data,
                        'critical_alerts': len(critical_alerts)
                    },
                    time.time() - start_time
                )
                return True
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка проверки системы алертов: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def test_sales_data_quality(self) -> bool:
        """Тест качества данных о продажах."""
        test_name = "Sales Data Quality"
        start_time = time.time()
        
        try:
            # Проверяем наличие данных за последние 7 дней
            result = self.ch_client.execute("""
                SELECT 
                    count() as rows_count,
                    min(event_date) as min_date,
                    max(event_date) as max_date,
                    sum(tickets_sold) as total_tickets,
                    sum(revenue - refunds) as net_revenue
                FROM zakaz.v_sales_latest
                WHERE event_date >= today() - 7
            """)
            
            if not result or not result.first_row:
                self.add_result(
                    test_name, 'warning', 'Нет данных о продажах за последние 7 дней',
                    duration=time.time() - start_time
                )
                return False
            
            data = result.first_row[0]
            
            if data['rows_count'] == 0:
                self.add_result(
                    test_name, 'warning', 'Нет данных о продажах за последние 7 дней',
                    duration=time.time() - start_time
                )
                return False
            
            # Проверяем на дубликаты
            dup_result = self.ch_client.execute("""
                SELECT count() as duplicates
                FROM (
                    SELECT 
                        event_date, 
                        city, 
                        event_name,
                        count() as cnt
                    FROM zakaz.v_sales_latest
                    WHERE event_date >= today() - 7
                    GROUP BY event_date, city, event_name
                    HAVING cnt > 1
                )
            """)
            
            duplicates = dup_result.first_row[0]['duplicates'] if dup_result and dup_result.first_row else 0
            
            if duplicates > 0:
                self.add_result(
                    test_name, 'warning', 
                    f'Обнаружены дубликаты в данных о продажах: {duplicates}',
                    {
                        'rows_count': data['rows_count'],
                        'min_date': str(data['min_date']),
                        'max_date': str(data['max_date']),
                        'total_tickets': data['total_tickets'],
                        'net_revenue': data['net_revenue'],
                        'duplicates': duplicates
                    },
                    time.time() - start_time
                )
                return False
            else:
                self.add_result(
                    test_name, 'ok', 'Данные о продажах качественные',
                    {
                        'rows_count': data['rows_count'],
                        'min_date': str(data['min_date']),
                        'max_date': str(data['max_date']),
                        'total_tickets': data['total_tickets'],
                        'net_revenue': data['net_revenue'],
                        'duplicates': duplicates
                    },
                    time.time() - start_time
                )
                return True
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка проверки качества данных о продажах: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def test_marketing_data_quality(self) -> bool:
        """Тест качества маркетинговых данных."""
        test_name = "Marketing Data Quality"
        start_time = time.time()
        
        try:
            # Проверяем наличие данных за последние 7 дней
            result = self.ch_client.execute("""
                SELECT 
                    count() as rows_count,
                    min(d) as min_date,
                    max(d) as max_date,
                    sum(net_revenue) as total_revenue,
                    sum(spend_total) as total_spend,
                    avg(romi) as avg_romi
                FROM zakaz.v_marketing_daily
                WHERE d >= today() - 7
            """)
            
            if not result or not result.first_row:
                self.add_result(
                    test_name, 'warning', 'Нет маркетинговых данных за последние 7 дней',
                    duration=time.time() - start_time
                )
                return False
            
            data = result.first_row[0]
            
            if data['rows_count'] == 0:
                self.add_result(
                    test_name, 'warning', 'Нет маркетинговых данных за последние 7 дней',
                    duration=time.time() - start_time
                )
                return False
            
            self.add_result(
                test_name, 'ok', 'Маркетинговые данные качественные',
                {
                    'rows_count': data['rows_count'],
                    'min_date': str(data['min_date']),
                    'max_date': str(data['max_date']),
                    'total_revenue': data['total_revenue'],
                    'total_spend': data['total_spend'],
                    'avg_romi': data['avg_romi']
                },
                time.time() - start_time
            )
            return True
                
        except Exception as e:
            self.add_result(
                test_name, 'error', f'Ошибка проверки качества маркетинговых данных: {str(e)}',
                duration=time.time() - start_time
            )
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Запуск всех тестов.
        
        Returns:
            Результаты тестирования
        """
        logger.info("Начало smoke-тестирования системы интеграций")
        
        # Запуск тестов
        tests = [
            self.test_clickhouse_connection,
            self.test_tables_exist,
            self.test_views_exist,
            self.test_data_freshness,
            self.test_job_runs,
            self.test_alerts,
            self.test_sales_data_quality,
            self.test_marketing_data_quality
        ]
        
        passed = 0
        failed = 0
        warnings = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Ошибка при выполнении теста: {e}")
                failed += 1
        
        # Формирование итогового результата
        total_time = time.time() - self.start_time.total_seconds()
        
        overall_status = 'ok'
        if failed > 0:
            overall_status = 'error'
        elif warnings > 0:
            overall_status = 'warning'
        
        summary = {
            'overall_status': overall_status,
            'timestamp': now_msk().isoformat(),
            'duration_seconds': round(total_time, 2),
            'tests': {
                'total': len(tests),
                'passed': passed,
                'failed': failed,
                'warnings': warnings
            },
            'results': self.results
        }
        
        # Вывод итогового результата
        status_symbol = {
            'ok': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(overall_status, '❓')
        
        logger.info(f"{status_symbol} Smoke-тестирование завершено: {passed}/{len(tests)} тестов пройдено")
        logger.info(f"Длительность: {round(total_time, 2)} секунд")
        
        if failed > 0:
            logger.error(f"Провалено {failed} тестов")
        elif warnings > 0:
            logger.warning(f"Есть {warnings} предупреждений")
        
        return summary

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='Smoke-тестирование системы интеграций')
    parser.add_argument('--env', type=str, default='secrets/.env.ch', 
                       help='Путь к файлу с переменными окружения')
    parser.add_argument('--output', type=str, help='Путь к файлу для сохранения результатов')
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
        
        # Создание и запуск smoke-тестера
        tester = SmokeTester(ch_client)
        results = tester.run_all_tests()
        
        # Сохранение результатов в файл
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Результаты сохранены в {args.output}")
        
        # Возврат кода завершения
        if results['overall_status'] == 'error':
            sys.exit(1)
        elif results['overall_status'] == 'warning':
            sys.exit(2)
        else:
            sys.exit(0)
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении smoke-тестирования: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()