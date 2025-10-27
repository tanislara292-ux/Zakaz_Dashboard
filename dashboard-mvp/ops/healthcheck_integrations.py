"""
Healthcheck endpoint для мониторинга состояния интеграций.
Предоставляет HTTP endpoint для проверки здоровья системы.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, setup_integrations_logger
)

# Настройка логгера
logger = setup_integrations_logger('healthcheck')

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP запросов для healthcheck."""
    
    def __init__(self, ch_client: ClickHouseClient, *args, **kwargs):
        self.ch_client = ch_client
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов."""
        if self.path == '/healthz':
            self.handle_healthcheck()
        elif self.path == '/healthz/detailed':
            self.handle_detailed_healthcheck()
        elif self.path == '/healthz/freshness':
            self.handle_freshness_check()
        elif self.path == '/healthz/qtickets_sheets':
            self.handle_qtickets_sheets_check()
        elif self.path == '/healthz/qtickets_api':
            self.handle_qtickets_api_check()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def handle_healthcheck(self):
        """Базовая проверка здоровья."""
        try:
            # Простая проверка подключения к ClickHouse
            result = self.ch_client.execute('SELECT 1')
            
            if result and result.first_row:
                response = {
                    'status': 'ok',
                    'timestamp': now_msk().isoformat(),
                    'checks': {
                        'clickhouse': 'ok'
                    }
                }
                self.send_json_response(200, response)
            else:
                response = {
                    'status': 'error',
                    'timestamp': now_msk().isoformat(),
                    'error': 'ClickHouse check failed'
                }
                self.send_json_response(503, response)
                
        except Exception as e:
            logger.error(f"Healthcheck failed: {e}")
            response = {
                'status': 'error',
                'timestamp': now_msk().isoformat(),
                'error': str(e)
            }
            self.send_json_response(503, response)
    
    def handle_detailed_healthcheck(self):
        """Детальная проверка здоровья."""
        try:
            checks = {}
            overall_status = 'ok'
            
            # Проверка ClickHouse
            try:
                result = self.ch_client.execute('SELECT 1')
                checks['clickhouse'] = {
                    'status': 'ok' if result and result.first_row else 'error',
                    'message': 'ClickHouse connection'
                }
            except Exception as e:
                checks['clickhouse'] = {
                    'status': 'error',
                    'message': f'ClickHouse error: {str(e)}'
                }
                overall_status = 'error'
            
            # Проверка свежести данных
            try:
                freshness_query = """
                SELECT 
                    source,
                    latest_date,
                    days_behind,
                    CASE 
                        WHEN days_behind <= 1 THEN 'ok'
                        WHEN days_behind <= 2 THEN 'warning'
                        ELSE 'error'
                    END as status
                FROM zakaz.v_data_freshness
                """
                
                result = self.ch_client.execute(freshness_query)
                freshness_checks = {}
                
                if result and result.first_row:
                    for row in result.first_row:
                        freshness_checks[row['source']] = {
                            'status': row['status'],
                            'latest_date': str(row['latest_date']),
                            'days_behind': row['days_behind']
                        }
                        
                        if row['status'] == 'error':
                            overall_status = 'error'
                        elif row['status'] == 'warning' and overall_status == 'ok':
                            overall_status = 'warning'
                
                checks['data_freshness'] = freshness_checks
            except Exception as e:
                checks['data_freshness'] = {
                    'status': 'error',
                    'message': f'Freshness check error: {str(e)}'
                }
                overall_status = 'error'
            
            # Проверка последних запусков задач
            try:
                jobs_query = """
                SELECT 
                    job,
                    status,
                    started_at,
                    CASE 
                        WHEN started_at >= now() - INTERVAL 1 HOUR AND status = 'success' THEN 'ok'
                        WHEN started_at >= now() - INTERVAL 6 HOUR AND status = 'success' THEN 'warning'
                        ELSE 'error'
                    END as recent_status
                FROM zakaz.meta_job_runs
                WHERE (job, started_at) IN (
                    SELECT job, max(started_at)
                    FROM zakaz.meta_job_runs
                    GROUP BY job
                )
                """
                
                result = self.ch_client.execute(jobs_query)
                jobs_checks = {}
                
                if result and result.first_row:
                    for row in result.first_row:
                        jobs_checks[row['job']] = {
                            'status': row['recent_status'],
                            'last_run': str(row['started_at']),
                            'last_status': row['status']
                        }
                        
                        if row['recent_status'] == 'error':
                            overall_status = 'error'
                        elif row['recent_status'] == 'warning' and overall_status == 'ok':
                            overall_status = 'warning'
                
                checks['job_runs'] = jobs_checks
            except Exception as e:
                checks['job_runs'] = {
                    'status': 'error',
                    'message': f'Jobs check error: {str(e)}'
                }
                overall_status = 'error'
            
            response = {
                'status': overall_status,
                'timestamp': now_msk().isoformat(),
                'checks': checks
            }
            
            # Определяем HTTP код ответа
            http_status = 200 if overall_status == 'ok' else 503
            self.send_json_response(http_status, response)
            
        except Exception as e:
            logger.error(f"Detailed healthcheck failed: {e}")
            response = {
                'status': 'error',
                'timestamp': now_msk().isoformat(),
                'error': str(e)
            }
            self.send_json_response(503, response)
    
    def handle_freshness_check(self):
        """Проверка свежести данных."""
        try:
            query = """
            SELECT 
                source,
                latest_date,
                days_behind,
                total_rows,
                CASE 
                    WHEN days_behind <= 1 THEN 'ok'
                    WHEN days_behind <= 2 THEN 'warning'
                    ELSE 'error'
                END as status
            FROM zakaz.v_data_freshness
            ORDER BY days_behind DESC
            """
            
            result = self.ch_client.execute(query)
            
            if result and result.first_row:
                freshness_data = []
                overall_status = 'ok'
                
                for row in result.first_row:
                    freshness_data.append({
                        'source': row['source'],
                        'latest_date': str(row['latest_date']),
                        'days_behind': row['days_behind'],
                        'total_rows': row['total_rows'],
                        'status': row['status']
                    })
                    
                    if row['status'] == 'error':
                        overall_status = 'error'
                    elif row['status'] == 'warning' and overall_status == 'ok':
                        overall_status = 'warning'
                
                response = {
                    'status': overall_status,
                    'timestamp': now_msk().isoformat(),
                    'data': freshness_data
                }
                
                http_status = 200 if overall_status == 'ok' else 503
                self.send_json_response(http_status, response)
            else:
                response = {
                    'status': 'error',
                    'timestamp': now_msk().isoformat(),
                    'error': 'No freshness data available'
                }
                self.send_json_response(503, response)
                
        except Exception as e:
            logger.error(f"Freshness check failed: {e}")
            response = {
                'status': 'error',
                'timestamp': now_msk().isoformat(),
                'error': str(e)
            }
            self.send_json_response(503, response)
    
    def handle_qtickets_sheets_check(self):
        """Проверка состояния qtickets_sheets интеграции."""
        try:
            checks = {}
            overall_status = 'ok'
            
            # Проверка последних запусков
            try:
                job_query = """
                SELECT
                    status,
                    started_at,
                    rows_processed,
                    message
                FROM zakaz.meta_job_runs
                WHERE job = 'qtickets_sheets'
                ORDER BY started_at DESC
                LIMIT 1
                """
                
                result = self.ch_client.execute(job_query)
                
                if result and result.first_row:
                    row = result.first_row[0]
                    time_since_run = (now_msk() - row['started_at']).total_seconds() / 60  # минуты
                    
                    if row['status'] == 'success' and time_since_run <= 20:  # 15 минут + погрешность
                        job_status = 'ok'
                    elif row['status'] == 'success' and time_since_run <= 60:
                        job_status = 'warning'
                    else:
                        job_status = 'error'
                    
                    checks['job_run'] = {
                        'status': job_status,
                        'last_run': str(row['started_at']),
                        'last_status': row['status'],
                        'rows_processed': row['rows_processed'],
                        'minutes_since_run': round(time_since_run, 2)
                    }
                    
                    if job_status == 'error':
                        overall_status = 'error'
                    elif job_status == 'warning' and overall_status == 'ok':
                        overall_status = 'warning'
                else:
                    checks['job_run'] = {
                        'status': 'error',
                        'message': 'No job runs found'
                    }
                    overall_status = 'error'
                    
            except Exception as e:
                checks['job_run'] = {
                    'status': 'error',
                    'message': f'Job run check error: {str(e)}'
                }
                overall_status = 'error'
            
            # Проверка свежести данных
            try:
                freshness_query = """
                SELECT
                    table_name,
                    latest_date,
                    days_behind,
                    total_rows
                FROM zakaz.v_qtickets_freshness
                """
                
                result = self.ch_client.execute(freshness_query)
                freshness_checks = {}
                
                if result and result.first_row:
                    for row in result.first_row:
                        status = 'ok' if row['days_behind'] <= 1 else 'warning' if row['days_behind'] <= 2 else 'error'
                        
                        freshness_checks[row['table_name']] = {
                            'status': status,
                            'latest_date': str(row['latest_date']),
                            'days_behind': row['days_behind'],
                            'total_rows': row['total_rows']
                        }
                        
                        if status == 'error':
                            overall_status = 'error'
                        elif status == 'warning' and overall_status == 'ok':
                            overall_status = 'warning'
                
                checks['data_freshness'] = freshness_checks
            except Exception as e:
                checks['data_freshness'] = {
                    'status': 'error',
                    'message': f'Freshness check error: {str(e)}'
                }
                overall_status = 'error'
            
            response = {
                'status': overall_status,
                'timestamp': now_msk().isoformat(),
                'integration': 'qtickets_sheets',
                'checks': checks
            }
            
            http_status = 200 if overall_status == 'ok' else 503
            self.send_json_response(http_status, response)
            
        except Exception as e:
            logger.error(f"QTickets Sheets healthcheck failed: {e}")
            response = {
                'status': 'error',
                'timestamp': now_msk().isoformat(),
                'integration': 'qtickets_sheets',
                'error': str(e)
            }
            self.send_json_response(503, response)

    def handle_qtickets_api_check(self):
        """�?�?�?�?��?��� QTickets API ��?�'��?�?���Ő��."""
        try:
            freshness_threshold = now_msk() - timedelta(hours=2)

            sales_query = """
            SELECT
                toDateTime(max(_ver)) AS last_loaded_at,
                count() AS rows_count
            FROM zakaz.fact_qtickets_sales_daily
            """
            inventory_query = """
            SELECT
                toDateTime(max(_ver)) AS last_loaded_at,
                count() AS rows_count
            FROM zakaz.fact_qtickets_inventory_latest
            """

            sales_row = self._row_as_dict(self.ch_client.execute(sales_query))
            inventory_row = self._row_as_dict(self.ch_client.execute(inventory_query))

            sales_ts = sales_row.get('last_loaded_at')
            inventory_ts = inventory_row.get('last_loaded_at')

            status = 'ok'
            details = {
                'sales_last_loaded_at': sales_ts.isoformat() if isinstance(sales_ts, datetime) else None,
                'inventory_last_loaded_at': inventory_ts.isoformat() if isinstance(inventory_ts, datetime) else None,
                'sales_rows': int(sales_row.get('rows_count') or 0),
                'inventory_rows': int(inventory_row.get('rows_count') or 0),
            }

            if not isinstance(sales_ts, datetime) or sales_ts < freshness_threshold:
                status = 'stale'
                details['sales_warning'] = 'fact_qtickets_sales_daily older than 2 hours'

            if not isinstance(inventory_ts, datetime) or inventory_ts < freshness_threshold:
                status = 'stale'
                details['inventory_warning'] = 'fact_qtickets_inventory_latest older than 2 hours'

            http_status = 200 if status == 'ok' else 500
            response = {
                'status': status,
                'timestamp': now_msk().isoformat(),
                'integration': 'qtickets_api',
                'details': details
            }
            self.send_json_response(http_status, response)

        except Exception as e:
            logger.error(f"QTickets API healthcheck failed: {e}")
            response = {
                'status': 'error',
                'timestamp': now_msk().isoformat(),
                'integration': 'qtickets_api',
                'error': str(e)
            }
            self.send_json_response(503, response)

    def _row_as_dict(self, result) -> Dict[str, Any]:
        """��������� ������ ClickHouse � dict ��� ������� �����."""
        if not result or not getattr(result, 'result_rows', None):
            return {}
        row = result.result_rows[0]
        return dict(zip(result.column_names, row))
    
    def send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Отправка JSON ответа."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        json_data = json.dumps(data, ensure_ascii=False, default=str)
        self.wfile.write(json_data.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Переопределение логирования для подавления вывода."""
        pass

def create_handler_class(ch_client: ClickHouseClient):
    """Создание класса обработчика с внедрением зависимостей."""
    
    class Handler(HealthCheckHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(ch_client, *args, **kwargs)
    
    return Handler

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='Healthcheck сервер')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Хост для привязки')
    parser.add_argument('--port', type=int, default=8080, help='Порт для привязки')
    parser.add_argument('--env', type=str, default='secrets/.env.ch',
                       help='Путь к файлу с переменными окружения')
    parser.add_argument('--check', type=str, help='Проверить конкретную интеграцию (qtickets_api, qtickets_sheets)')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    try:
        # Инициализация клиента ClickHouse
        ch_client = get_client(args.env)
        
        # Если указан флаг --check, выполняем проверку и выходим
        if args.check:
            handler_class = create_handler_class(ch_client)
            handler = handler_class()
            
            if args.check == 'qtickets_api':
                handler.handle_qtickets_api_check()
            elif args.check == 'qtickets_sheets':
                handler.handle_qtickets_sheets_check()
            else:
                print(f"Неизвестная интеграция: {args.check}")
                sys.exit(1)
            return
        
        # Создание обработчика с внедрением зависимостей
        handler_class = create_handler_class(ch_client)
        
        # Запуск HTTP сервера
        server = HTTPServer((args.host, args.port), handler_class)
        logger.info(f"Healthcheck сервер запущен на {args.host}:{args.port}")
        logger.info("Эндпоинты:")
        logger.info("  GET /healthz - базовая проверка")
        logger.info("  GET /healthz/detailed - детальная проверка")
        logger.info("  GET /healthz/freshness - проверка свежести данных")
        logger.info("  GET /healthz/qtickets_sheets - проверка qtickets_sheets интеграции")
        logger.info("  GET /healthz/qtickets_api - проверка qtickets_api интеграции")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        logger.info("Остановка сервера...")
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
