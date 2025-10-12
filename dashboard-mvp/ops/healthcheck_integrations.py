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
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    try:
        # Инициализация клиента ClickHouse
        ch_client = get_client(args.env)
        
        # Создание обработчика с внедрением зависимостей
        handler_class = create_handler_class(ch_client)
        
        # Запуск HTTP сервера
        server = HTTPServer((args.host, args.port), handler_class)
        logger.info(f"Healthcheck сервер запущен на {args.host}:{args.port}")
        logger.info("Эндпоинты:")
        logger.info("  GET /healthz - базовая проверка")
        logger.info("  GET /healthz/detailed - детальная проверка")
        logger.info("  GET /healthz/freshness - проверка свежести данных")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        logger.info("Остановка сервера...")
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()