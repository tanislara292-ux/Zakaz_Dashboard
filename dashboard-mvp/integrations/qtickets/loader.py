"""
QTickets API загрузчик.
Загружает данные о мероприятиях, продажах и инвентаре из QTickets API.
"""

import os
import sys
import argparse
import json
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, today_msk, to_date, days_ago,
    setup_integrations_logger, log_data_operation
)

# Настройка логгера
logger = setup_integrations_logger('qtickets')

class QTicketsAPIClient:
    """Клиент для работы с QTickets API."""
    
    def __init__(self, token: str, api_url: str = None, timeout: int = 30):
        """
        Инициализация клиента QTickets API.
        
        Args:
            token: API токен
            api_url: URL API
            timeout: Таймаут запросов
        """
        self.token = token
        self.api_url = api_url or os.getenv('QTICKETS_API_URL', 'https://api.qtickets.ru/v1')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполнение запроса к API.
        
        Args:
            endpoint: Эндпоинт API
            params: Параметры запроса
            
        Returns:
            Ответ API в виде словаря
        """
        url = f"{self.api_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к QTickets API: {e}")
            raise
    
    def fetch_events(self) -> List[Dict[str, Any]]:
        """
        Получение списка мероприятий.
        
        Returns:
            Список мероприятий
        """
        logger.info("Загрузка списка мероприятий из QTickets API")
        
        try:
            data = self._make_request('events')
            events = data.get('events', [])
            
            logger.info(f"Загружено {len(events)} мероприятий")
            return events
        except Exception as e:
            logger.error(f"Ошибка при загрузке мероприятий: {e}")
            raise
    
    def fetch_event_details(self, event_id: str) -> Dict[str, Any]:
        """
        Получение детальной информации о мероприятии.
        
        Args:
            event_id: ID мероприятия
            
        Returns:
            Детальная информация о мероприятии
        """
        logger.debug(f"Загрузка деталей мероприятия {event_id}")
        
        try:
            data = self._make_request(f'events/{event_id}')
            return data.get('event', {})
        except Exception as e:
            logger.error(f"Ошибка при загрузке деталей мероприятия {event_id}: {e}")
            raise
    
    def fetch_inventory(self, event_id: str) -> Dict[str, Any]:
        """
        Получение информации об инвентаре (доступные билеты).
        
        Args:
            event_id: ID мероприятия
            
        Returns:
            Информация об инвентаре
        """
        logger.debug(f"Загрузка инвентаря для мероприятия {event_id}")
        
        try:
            data = self._make_request(f'events/{event_id}/inventory')
            return data.get('inventory', {})
        except Exception as e:
            logger.error(f"Ошибка при загрузке инвентаря для мероприятия {event_id}: {e}")
            raise
    
    def fetch_sales(self, date_from: date = None, date_to: date = None) -> List[Dict[str, Any]]:
        """
        Получение данных о продажах за период.
        
        Args:
            date_from: Начальная дата
            date_to: Конечная дата
            
        Returns:
            Список продаж
        """
        if not date_from:
            date_from = days_ago(int(os.getenv('QTICKETS_DAYS_BACK', 30)))
        if not date_to:
            date_to = today_msk()
        
        logger.info(f"Загрузка данных о продажах за период {date_from} - {date_to}")
        
        params = {
            'date_from': date_from.strftime('%Y-%m-%d'),
            'date_to': date_to.strftime('%Y-%m-%d')
        }
        
        try:
            data = self._make_request('sales', params)
            sales = data.get('sales', [])
            
            logger.info(f"Загружено {len(sales)} записей о продажах")
            return sales
        except Exception as e:
            logger.error(f"Ошибка при загрузке продаж: {e}")
            raise

class QTicketsLoader:
    """Загрузчик данных QTickets в ClickHouse."""
    
    def __init__(self, ch_client: ClickHouseClient, api_client: QTicketsAPIClient):
        """
        Инициализация загрузчика.
        
        Args:
            ch_client: Клиент ClickHouse
            api_client: Клиент QTickets API
        """
        self.ch_client = ch_client
        self.api_client = api_client
    
    def normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализация данных мероприятия.
        
        Args:
            event: Сырые данные мероприятия
            
        Returns:
            Нормализованные данные
        """
        try:
            # Получение инвентаря
            inventory = self.api_client.fetch_inventory(event.get('id'))
            
            return {
                'event_id': str(event.get('id')),
                'event_name': event.get('name', '').strip(),
                'event_date': to_date(event.get('date')),
                'city': event.get('city', '').strip().lower(),
                'tickets_total': int(inventory.get('total_tickets', 0)),
                'tickets_left': int(inventory.get('available_tickets', 0)),
                '_ver': now_msk()
            }
        except Exception as e:
            logger.warning(f"Ошибка при нормализации мероприятия {event.get('id')}: {e}")
            return None
    
    def normalize_sale(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализация данных продажи.
        
        Args:
            sale: Сырые данные продажи
            
        Returns:
            Нормализованные данные
        """
        try:
            return {
                'src_msg_id': '',  # Пусто для API данных
                'ingested_at': now_msk(),
                'event_date': to_date(sale.get('event_date')),
                'event_id': str(sale.get('event_id')),
                'event_name': sale.get('event_name', '').strip(),
                'city': sale.get('city', '').strip().lower(),
                'tickets_sold': int(sale.get('tickets_sold', 0)),
                'revenue': float(Decimal(str(sale.get('revenue', 0)))),
                'refunds': float(Decimal(str(sale.get('refunds', 0)))),
                'currency': sale.get('currency', 'RUB'),
                '_ver': now_msk()
            }
        except Exception as e:
            logger.warning(f"Ошибка при нормализации продажи {sale.get('id')}: {e}")
            return None
    
    @log_data_operation(logger, 'load', 'qtickets_api', 'clickhouse')
    def load_events(self) -> int:
        """
        Загрузка мероприятий в ClickHouse.
        
        Returns:
            Количество загруженных мероприятий
        """
        logger.info("Начало загрузки мероприятий")
        
        try:
            # Получение мероприятий из API
            events_raw = self.api_client.fetch_events()
            
            # Нормализация данных
            events = []
            for event_raw in events_raw:
                event = self.normalize_event(event_raw)
                if event:
                    events.append(event)
            
            if not events:
                logger.warning("Нет мероприятий для загрузки")
                return 0
            
            # Загрузка в ClickHouse
            self.ch_client.insert('zakaz.dim_events', events)
            
            logger.info(f"Загружено {len(events)} мероприятий")
            return len(events)
        except Exception as e:
            logger.error(f"Ошибка при загрузке мероприятий: {e}")
            raise
    
    @log_data_operation(logger, 'load', 'qtickets_api', 'clickhouse')
    def load_sales(self, date_from: date = None, date_to: date = None) -> int:
        """
        Загрузка продаж в ClickHouse.
        
        Args:
            date_from: Начальная дата
            date_to: Конечная дата
            
        Returns:
            Количество загруженных продаж
        """
        logger.info(f"Начало загрузки продаж за период {date_from} - {date_to}")
        
        try:
            # Получение продаж из API
            sales_raw = self.api_client.fetch_sales(date_from, date_to)
            
            # Нормализация данных
            sales = []
            for sale_raw in sales_raw:
                sale = self.normalize_sale(sale_raw)
                if sale:
                    sales.append(sale)
            
            if not sales:
                logger.warning("Нет продаж для загрузки")
                return 0
            
            # Загрузка в ClickHouse
            self.ch_client.insert('zakaz.stg_qtickets_sales_raw', sales)
            
            logger.info(f"Загружено {len(sales)} записей о продажах")
            return len(sales)
        except Exception as e:
            logger.error(f"Ошибка при загрузке продаж: {e}")
            raise
    
    def load_all(self, date_from: date = None, date_to: date = None) -> Dict[str, int]:
        """
        Полная загрузка данных (мероприятия и продажи).
        
        Args:
            date_from: Начальная дата для продаж
            date_to: Конечная дата для продаж
            
        Returns:
            Словарь с количеством загруженных записей
        """
        logger.info("Начало полной загрузки данных QTickets")
        
        results = {}
        
        # Загрузка мероприятий
        try:
            results['events'] = self.load_events()
        except Exception as e:
            logger.error(f"Ошибка при загрузке мероприятий: {e}")
            results['events'] = 0
        
        # Загрузка продаж
        try:
            results['sales'] = self.load_sales(date_from, date_to)
        except Exception as e:
            logger.error(f"Ошибка при загрузке продаж: {e}")
            results['sales'] = 0
        
        logger.info(f"Загрузка завершена: {results}")
        return results

def record_job_run(ch_client: ClickHouseClient, job: str, status: str, 
                  rows_processed: int = 0, message: str = "", 
                  metrics: Dict[str, Any] = None) -> None:
    """
    Запись информации о запуске задачи в ClickHouse.
    
    Args:
        ch_client: Клиент ClickHouse
        job: Название задачи
        status: Статус (success, error, running)
        rows_processed: Количество обработанных строк
        message: Сообщение
        metrics: Метрики
    """
    try:
        run_data = {
            'job': job,
            'started_at': now_msk(),
            'finished_at': now_msk(),
            'rows_processed': rows_processed,
            'status': status,
            'message': message,
            'metrics': json.dumps(metrics or {})
        }
        
        ch_client.insert('zakaz.meta_job_runs', [run_data])
    except Exception as e:
        logger.error(f"Ошибка при записи информации о запуске задачи: {e}")

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='QTickets загрузчик')
    parser.add_argument('--days', type=int, help='Количество дней для загрузки')
    parser.add_argument('--since', type=str, help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--to', type=str, help='Конечная дата в формате YYYY-MM-DD')
    parser.add_argument('--env', type=str, default='secrets/.env.qtickets', 
                       help='Путь к файлу с переменными окружения')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    # Определение периода загрузки
    date_from = None
    date_to = today_msk()
    
    if args.since:
        date_from = to_date(args.since)
    elif args.days:
        date_from = days_ago(args.days)
    else:
        date_from = days_ago(int(os.getenv('QTICKETS_DAYS_BACK', 30)))
    
    if args.to:
        date_to = to_date(args.to)
    
    try:
        # Инициализация клиентов
        ch_client = get_client(args.env)
        api_client = QTicketsAPIClient(
            token=os.getenv('QTICKETS_TOKEN'),
            api_url=os.getenv('QTICKETS_API_URL'),
            timeout=int(os.getenv('QTICKETS_TIMEOUT', 30))
        )
        
        loader = QTicketsLoader(ch_client, api_client)
        
        # Запись о начале работы
        record_job_run(ch_client, 'qtickets_loader', 'running')
        
        # Загрузка данных
        results = loader.load_all(date_from, date_to)
        
        # Запись об успешном завершении
        total_rows = sum(results.values())
        record_job_run(
            ch_client, 'qtickets_loader', 'success', 
            total_rows, f"Загружено: {results}", results
        )
        
        logger.info(f"Загрузка успешно завершена: {results}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении загрузчика: {e}")
        
        # Попытка записи об ошибке
        try:
            ch_client = get_client(args.env)
            record_job_run(ch_client, 'qtickets_loader', 'error', 0, str(e))
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main()