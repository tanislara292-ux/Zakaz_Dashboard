#!/usr/bin/env python3
"""
Инкрементальный загрузчик для QTickets CDC.
"""
import os
import logging
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
import time
import json

import clickhouse_connect
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QTicketsCDCLoader:
    """Класс для инкрементальной загрузки данных QTickets."""
    
    def __init__(self):
        """Инициализация загрузчика."""
        load_dotenv()
        
        # ClickHouse настройки
        self.ch_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.ch_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.ch_user = os.getenv('CLICKHOUSE_USER', 'etl_writer')
        self.ch_password = os.getenv('CLICKHOUSE_PASSWORD')
        self.ch_database = os.getenv('CLICKHOUSE_DATABASE', 'zakaz')
        
        # QTickets API настройки
        self.qtickets_api_url = os.getenv('QTICKETS_API_URL', 'https://api.qtickets.com/v1')
        self.qtickets_api_token = os.getenv('QTICKETS_API_TOKEN')
        
        # NRT настройки
        self.nrt_interval_min = int(os.getenv('NRT_INTERVAL_MIN', '10'))
        self.safety_lag_min = int(os.getenv('SAFETY_LAG_MIN', '45'))
        self.cdc_window_days = int(os.getenv('CDC_WINDOW_DAYS', '3'))
        
        # Инициализация клиентов
        self._init_clickhouse_client()
        self._init_session()
    
    def _init_clickhouse_client(self):
        """Инициализация ClickHouse клиента."""
        try:
            self.ch_client = clickhouse_connect.get_client(
                host=self.ch_host,
                port=self.ch_port,
                username=self.ch_user,
                password=self.ch_password,
                database=self.ch_database
            )
            logger.info("ClickHouse клиент инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации ClickHouse клиента: {e}")
            raise
    
    def _init_session(self):
        """Инициализация HTTP сессии."""
        self.session = requests.Session()
        if self.qtickets_api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.qtickets_api_token}',
                'Content-Type': 'application/json'
            })
        logger.info("HTTP сессия инициализирована")
    
    def get_watermark(self, source: str, stream: str, wm_type: str) -> Optional[str]:
        """Получение водяного знака из meta.watermarks."""
        try:
            query = """
            SELECT wm_value_s 
            FROM meta.watermarks 
            WHERE source = %(source)s AND stream = %(stream)s AND wm_type = %(wm_type)s
            ORDER BY updated_at DESC 
            LIMIT 1
            """
            
            result = self.ch_client.query(
                query,
                parameters={
                    'source': source,
                    'stream': stream,
                    'wm_type': wm_type
                }
            )
            
            if result.result_rows:
                return result.result_rows[0][0]
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения водяного знака: {e}")
            return None
    
    def update_watermark(self, source: str, stream: str, wm_type: str, wm_value: str):
        """Обновление водяного знака в meta.watermarks."""
        try:
            insert_sql = """
            INSERT INTO meta.watermarks (source, stream, wm_type, wm_value_s, updated_at)
            VALUES (%(source)s, %(stream)s, %(wm_type)s, %(wm_value)s, now())
            """
            
            self.ch_client.command(
                insert_sql,
                parameters={
                    'source': source,
                    'stream': stream,
                    'wm_type': wm_type,
                    'wm_value': wm_value
                }
            )
            
            logger.debug(f"Водяной знак обновлен: {source}.{stream}.{wm_type} = {wm_value}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления водяного знака: {e}")
            raise
    
    def fetch_orders(self, from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
        """Получение заказов из QTickets API за период."""
        logger.info(f"Загрузка заказов за период {from_date} - {to_date}")
        
        orders = []
        page = 1
        page_size = 1000
        
        while True:
            try:
                # Формируем параметры запроса
                params = {
                    'page': page,
                    'limit': page_size,
                    'updated_from': from_date.isoformat(),
                    'updated_to': to_date.isoformat(),
                    'sort': 'updated_at'
                }
                
                response = self.session.get(
                    f"{self.qtickets_api_url}/orders",
                    params=params,
                    timeout=30
                )
                
                response.raise_for_status()
                data = response.json()
                
                if not data.get('data'):
                    break
                
                orders.extend(data['data'])
                
                # Проверяем, есть ли еще страницы
                if len(data['data']) < page_size:
                    break
                
                page += 1
                logger.debug(f"Загружена страница {page}, всего заказов: {len(orders)}")
                
                # Небольшая задержка между запросами
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки страницы {page}: {e}")
                raise
        
        logger.info(f"Загружено {len(orders)} заказов за период {from_date} - {to_date}")
        return orders
    
    def transform_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Трансформация заказа в формат стейджинга."""
        try:
            # Извлекаем необходимые поля
            event_date = datetime.fromisoformat(order['event_date']).date()
            event_id = str(order['event_id'])
            city = order.get('city', '').lower().strip()
            order_id = str(order['id'])
            tickets_sold = int(order.get('tickets_count', 0))
            net_revenue = float(order.get('total_amount', 0)) - float(order.get('refund_amount', 0))
            currency = order.get('currency', 'RUB')
            
            # Определяем операцию
            _op = 'UPSERT'
            if order.get('status') == 'cancelled' and order.get('refund_amount', 0) > 0:
                _op = 'DELETE'
            
            # Формируем запись
            now_dt = datetime.now()
            return {
                'event_date': event_date,
                'event_id': event_id,
                'city': city,
                'order_id': order_id,
                'tickets_sold': tickets_sold,
                'net_revenue': net_revenue,
                'currency': currency,
                
                '_src': 'qtickets',
                '_op': _op,
                '_ver': int(now_dt.timestamp() * 1000),
                '_loaded_at': now_dt
            }
            
        except Exception as e:
            logger.error(f"Ошибка трансформации заказа {order.get('id', 'unknown')}: {e}")
            raise
    
    def insert_to_staging(self, orders: List[Dict[str, Any]], batch_size: int = 5000):
        """Вставка заказов в стейджинг таблицу."""
        if not orders:
            logger.info("Нет заказов для вставки")
            return
        
        logger.info(f"Вставка {len(orders)} заказов в стейджинг")
        
        # Разбиваем на батчи
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            
            try:
                self.ch_client.insert(
                    'zakaz.stg_sales_events',
                    batch,
                    column_names=[
                        'event_date', 'event_id', 'city', 'order_id', 
                        'tickets_sold', 'net_revenue', 'currency',
                        '_src', '_op', '_ver', '_loaded_at'
                    ]
                )
                
                logger.debug(f"Вставлен батч {i//batch_size + 1}, размер: {len(batch)}")
                
            except Exception as e:
                logger.error(f"Ошибка вставки батча {i//batch_size + 1}: {e}")
                raise
        
        logger.info(f"Успешно вставлено {len(orders)} заказов в стейджинг")
    
    def run_cdc(self, minutes: Optional[int] = None):
        """Основной метод выполнения CDC загрузки."""
        if minutes is None:
            minutes = self.nrt_interval_min
        
        # Определяем окно загрузки
        now = datetime.now()
        to_date = now - timedelta(minutes=self.safety_lag_min)
        from_date = to_date - timedelta(days=self.cdc_window_days)
        
        # Получаем водяной знак
        watermark = self.get_watermark('qtickets', 'orders', 'updated_at')
        if watermark:
            try:
                watermark_dt = datetime.fromisoformat(watermark)
                from_date = max(from_date, watermark_dt)
            except ValueError:
                logger.warning(f"Неверный формат водяного знака: {watermark}, используем по умолчанию")
        
        logger.info(f"Окно загрузки: {from_date} - {to_date}")
        
        try:
            # Шаг 1: Загрузка данных из источника
            orders = self.fetch_orders(from_date, to_date)
            
            # Шаг 2: Трансформация данных
            transformed_orders = [self.transform_order(order) for order in orders]
            
            # Шаг 3: Вставка в стейджинг
            self.insert_to_staging(transformed_orders)
            
            # Шаг 4: Обновление водяного знака
            # Используем to_date - safety_lag_min чтобы оставить перекрытие
            new_watermark = (to_date - timedelta(minutes=self.safety_lag_min)).isoformat()
            self.update_watermark('qtickets', 'orders', 'updated_at', new_watermark)
            
            logger.info(f"CDC загрузка завершена успешно. Обработано заказов: {len(transformed_orders)}")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении CDC загрузки: {e}")
            raise


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Инкрементальная загрузка QTickets CDC'
    )
    
    # Параметры загрузки
    parser.add_argument(
        '--minutes',
        type=int,
        help='Интервал загрузки в минутах'
    )
    
    # ClickHouse параметры
    parser.add_argument(
        '--ch-host',
        type=str,
        default=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        help='ClickHouse хост'
    )
    parser.add_argument(
        '--ch-port',
        type=int,
        default=int(os.getenv('CLICKHOUSE_PORT', '8123')),
        help='ClickHouse порт'
    )
    parser.add_argument(
        '--ch-user',
        type=str,
        default=os.getenv('CLICKHOUSE_USER', 'etl_writer'),
        help='ClickHouse пользователь'
    )
    parser.add_argument(
        '--ch-pass',
        type=str,
        default=os.getenv('CLICKHOUSE_PASSWORD'),
        help='ClickHouse пароль'
    )
    parser.add_argument(
        '--ch-database',
        type=str,
        default=os.getenv('CLICKHOUSE_DATABASE', 'zakaz'),
        help='ClickHouse база данных'
    )
    
    # Другие параметры
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробное логирование'
    )
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    try:
        # Установка переменных окружения из аргументов
        os.environ['CLICKHOUSE_HOST'] = args.ch_host
        os.environ['CLICKHOUSE_PORT'] = str(args.ch_port)
        os.environ['CLICKHOUSE_USER'] = args.ch_user
        os.environ['CLICKHOUSE_PASSWORD'] = args.ch_pass
        os.environ['CLICKHOUSE_DATABASE'] = args.ch_database
        
        # Создание и запуск загрузчика
        loader = QTicketsCDCLoader()
        loader.run_cdc(minutes=args.minutes)
        
        logger.info("Загрузка завершена успешно")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Загрузка прервана пользователем")
        return 1
    except Exception as e:
        logger.error(f"Ошибка при загрузке: {e}")
        return 1


if __name__ == "__main__":
    exit(main())