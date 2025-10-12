"""
Скрипт для построения материализованной витрины продаж dm_sales_daily.
"""
import os
import logging
import argparse
from datetime import datetime, date, timedelta
from typing import Optional

import clickhouse_connect
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DmSalesBuilder:
    """Класс для построения витрины продаж."""
    
    def __init__(self):
        """Инициализация билдера."""
        load_dotenv()
        
        # ClickHouse настройки
        self.ch_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.ch_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.ch_user = os.getenv('CLICKHOUSE_USER', 'etl_writer')
        self.ch_password = os.getenv('CLICKHOUSE_PASSWORD')
        self.ch_database = os.getenv('CLICKHOUSE_DATABASE', 'zakaz')
        
        # Инициализация клиента
        self._init_clickhouse_client()
    
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
    
    def _parse_date(self, date_str: str) -> date:
        """Парсинг даты из строки."""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Неверный формат даты: {date_str}")
            raise
    
    def delete_range(self, from_date: date, to_date: date):
        """Удаление целевого диапазона из витрины."""
        logger.info(f"Удаление данных из витрины за период {from_date} - {to_date}")
        
        try:
            alter_sql = """
            ALTER TABLE zakaz.dm_sales_daily DELETE 
            WHERE event_date BETWEEN %(from_date)s AND %(to_date)s
            """
            
            self.ch_client.command(
                alter_sql,
                parameters={
                    'from_date': from_date,
                    'to_date': to_date
                }
            )
            
            logger.info(f"Данные за период {from_date} - {to_date} удалены из витрины")
            
        except Exception as e:
            logger.error(f"Ошибка при удалении данных из витрины: {e}")
            raise
    
    def build_materialized_view(self, from_date: date, to_date: date):
        """Построение материализованной витрины."""
        logger.info(f"Построение витрины за период {from_date} - {to_date}")
        
        try:
            insert_sql = """
            INSERT INTO zakaz.dm_sales_daily
            SELECT
                toDate(event_date)        AS event_date,
                toDate(report_date)       AS sale_date,
                city,
                event_name,
                sum(tickets_sold)         AS tickets_sold,
                toUInt64(sum(revenue) * 100)        AS revenue,
                toUInt64(sum(refunds_amount) * 100) AS refunds_amount,
                toInt64((sum(revenue) - sum(refunds_amount)) * 100) AS net_revenue,
                toUInt64(toUnixTimestamp(now()))     AS _ver
            FROM zakaz.stg_qtickets_sales FINAL
            WHERE event_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY event_date, sale_date, city, event_name
            """
            
            result = self.ch_client.command(
                insert_sql,
                parameters={
                    'from_date': from_date,
                    'to_date': to_date
                }
            )
            
            logger.info(f"Витрина построена успешно. Обработано строк: {result}")
            
        except Exception as e:
            logger.error(f"Ошибка при построении витрины: {e}")
            raise
    
    def build_dm_sales(self, from_date: Optional[date] = None, 
                      to_date: Optional[date] = None, days: Optional[int] = None):
        """Основной метод построения витрины."""
        
        # Определение диапазона дат
        if days is not None:
            to_date = date.today()
            from_date = to_date - timedelta(days=days)
        elif from_date is None or to_date is None:
            logger.error("Необходимо указать либо days, либо from_date и to_date")
            raise ValueError("Необходимо указать либо days, либо from_date и to_date")
        
        logger.info(f"Запуск построения витрины dm_sales_daily за период {from_date} - {to_date}")
        
        try:
            # Шаг 1: Удаление целевого диапазона из витрины
            self.delete_range(from_date, to_date)
            
            # Шаг 2: Вставка "с нуля" с учетом dedup на источнике
            self.build_materialized_view(from_date, to_date)
            
            logger.info("Построение витрины dm_sales_daily завершено успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при построении витрины: {e}")
            raise


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Построение материализованной витрины продаж dm_sales_daily'
    )
    
    # Параметры дат
    parser.add_argument(
        '--from',
        type=str,
        dest='from_date',
        help='Начальная дата (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--to',
        type=str,
        dest='to_date',
        help='Конечная дата (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Количество дней от сегодняшней даты'
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
        
        # Парсинг дат
        from_date = None
        to_date = None
        
        if args.from_date:
            from_date = datetime.strptime(args.from_date, '%Y-%m-%d').date()
        if args.to_date:
            to_date = datetime.strptime(args.to_date, '%Y-%m-%d').date()
        
        # Создание и запуск билдера
        builder = DmSalesBuilder()
        builder.build_dm_sales(
            from_date=from_date,
            to_date=to_date,
            days=args.days
        )
        
        logger.info("Построение витрины завершено успешно")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Построение прервано пользователем")
        return 1
    except Exception as e:
        logger.error(f"Ошибка при построении витрины: {e}")
        return 1


if __name__ == "__main__":
    exit(main())