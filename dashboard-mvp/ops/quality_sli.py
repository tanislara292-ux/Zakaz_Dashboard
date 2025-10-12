#!/usr/bin/env python3
"""
Расчет SLI для мониторинга качества данных.
"""
import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple

import clickhouse_connect
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SLICalculator:
    """Класс для расчета SLI показателей."""
    
    def __init__(self):
        """Инициализация калькулятора."""
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
    
    def calculate_freshness_sales(self, target_date: date) -> float:
        """Расчет свежести данных для продаж."""
        try:
            query = """
            SELECT max(_loaded_at) AS max_loaded_at
            FROM zakaz.dm_sales_daily
            WHERE event_date = %(target_date)s
            """
            
            result = self.ch_client.query(
                query,
                parameters={'target_date': target_date}
            )
            
            if result.result_rows and result.result_rows[0][0]:
                max_loaded_at = result.result_rows[0][0]
                now = datetime.now()
                freshness_hours = (now - max_loaded_at).total_seconds() / 3600
                return max(0, freshness_hours)
            
            return 24.0  # Если данных нет, считаем свежесть 24 часа
            
        except Exception as e:
            logger.error(f"Ошибка расчета свежести продаж: {e}")
            return 24.0
    
    def calculate_freshness_vk(self, target_date: date) -> float:
        """Расчет свежести данных для VK Ads."""
        try:
            query = """
            SELECT max(_loaded_at) AS max_loaded_at
            FROM zakaz.dm_vk_ads_daily
            WHERE stat_date = %(target_date)s
            """
            
            result = self.ch_client.query(
                query,
                parameters={'target_date': target_date}
            )
            
            if result.result_rows and result.result_rows[0][0]:
                max_loaded_at = result.result_rows[0][0]
                now = datetime.now()
                freshness_hours = (now - max_loaded_at).total_seconds() / 3600
                return max(0, freshness_hours)
            
            return 24.0  # Если данных нет, считаем свежесть 24 часа
            
        except Exception as e:
            logger.error(f"Ошибка расчета свежести VK Ads: {e}")
            return 24.0
    
    def calculate_completeness_sales(self, target_date: date) -> float:
        """Расчет полноты данных для продаж."""
        try:
            # Проверяем наличие данных в стейджинге и витрине
            staging_query = """
            SELECT count() AS cnt
            FROM zakaz.stg_sales_events
            WHERE event_date = %(target_date)s
            """
            
            mart_query = """
            SELECT count() AS cnt
            FROM zakaz.dm_sales_daily
            WHERE event_date = %(target_date)s
            """
            
            staging_result = self.ch_client.query(
                staging_query,
                parameters={'target_date': target_date}
            )
            
            mart_result = self.ch_client.query(
                mart_query,
                parameters={'target_date': target_date}
            )
            
            staging_count = staging_result.result_rows[0][0] if staging_result.result_rows else 0
            mart_count = mart_result.result_rows[0][0] if mart_result.result_rows else 0
            
            # Полнота = отношение данных в витрине к данным в стейджинге
            if staging_count > 0:
                return min(1.0, mart_count / staging_count)
            
            return 1.0 if mart_count == 0 else 0.0
            
        except Exception as e:
            logger.error(f"Ошибка расчета полноты продаж: {e}")
            return 0.0
    
    def calculate_completeness_vk(self, target_date: date) -> float:
        """Расчет полноты данных для VK Ads."""
        try:
            # Проверяем наличие данных в стейджинге и витрине
            staging_query = """
            SELECT count() AS cnt
            FROM zakaz.stg_vk_ads_daily
            WHERE stat_date = %(target_date)s
            """
            
            mart_query = """
            SELECT count() AS cnt
            FROM zakaz.dm_vk_ads_daily
            WHERE stat_date = %(target_date)s
            """
            
            staging_result = self.ch_client.query(
                staging_query,
                parameters={'target_date': target_date}
            )
            
            mart_result = self.ch_client.query(
                mart_query,
                parameters={'target_date': target_date}
            )
            
            staging_count = staging_result.result_rows[0][0] if staging_result.result_rows else 0
            mart_count = mart_result.result_rows[0][0] if mart_result.result_rows else 0
            
            # Полнота = отношение данных в витрине к данным в стейджинге
            if staging_count > 0:
                return min(1.0, mart_count / staging_count)
            
            return 1.0 if mart_count == 0 else 0.0
            
        except Exception as e:
            logger.error(f"Ошибка расчета полноты VK Ads: {e}")
            return 0.0
    
    def calculate_latency_sales(self, target_date: date) -> float:
        """Расчет задержки обработки для продаж."""
        try:
            query = """
            SELECT 
                min(_loaded_at) AS min_loaded_at,
                max(event_date) AS max_event_date
            FROM zakaz.stg_sales_events
            WHERE event_date = %(target_date)s
            """
            
            result = self.ch_client.query(
                query,
                parameters={'target_date': target_date}
            )
            
            if result.result_rows and result.result_rows[0][0] and result.result_rows[0][1]:
                min_loaded_at = result.result_rows[0][0]
                max_event_date = result.result_rows[0][1]
                
                # Конвертируем дату события в datetime
                max_event_dt = datetime.combine(max_event_date, datetime.min.time())
                
                # Задержка в часах
                latency_hours = (min_loaded_at - max_event_dt).total_seconds() / 3600
                return max(0, latency_hours)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Ошибка расчета задержки продаж: {e}")
            return 0.0
    
    def calculate_latency_vk(self, target_date: date) -> float:
        """Расчет задержки обработки для VK Ads."""
        try:
            query = """
            SELECT 
                min(_loaded_at) AS min_loaded_at,
                max(stat_date) AS max_stat_date
            FROM zakaz.stg_vk_ads_daily
            WHERE stat_date = %(target_date)s
            """
            
            result = self.ch_client.query(
                query,
                parameters={'target_date': target_date}
            )
            
            if result.result_rows and result.result_rows[0][0] and result.result_rows[0][1]:
                min_loaded_at = result.result_rows[0][0]
                max_stat_date = result.result_rows[0][1]
                
                # Конвертируем дату события в datetime
                max_stat_dt = datetime.combine(max_stat_date, datetime.min.time())
                
                # Задержка в часах
                latency_hours = (min_loaded_at - max_stat_dt).total_seconds() / 3600
                return max(0, latency_hours)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Ошибка расчета задержки VK Ads: {e}")
            return 0.0
    
    def calculate_all_sli(self, target_date: date) -> List[Tuple]:
        """Расчет всех SLI для указанной даты."""
        sli_records = []
        
        # Свежесть данных
        sales_freshness = self.calculate_freshness_sales(target_date)
        vk_freshness = self.calculate_freshness_vk(target_date)
        
        sli_records.append((target_date, 'dm_sales_daily', 'freshness_hours', sales_freshness))
        sli_records.append((target_date, 'dm_vk_ads_daily', 'freshness_hours', vk_freshness))
        
        # Полнота данных
        sales_completeness = self.calculate_completeness_sales(target_date)
        vk_completeness = self.calculate_completeness_vk(target_date)
        
        sli_records.append((target_date, 'dm_sales_daily', 'completeness_ratio', sales_completeness))
        sli_records.append((target_date, 'dm_vk_ads_daily', 'completeness_ratio', vk_completeness))
        
        # Задержка обработки
        sales_latency = self.calculate_latency_sales(target_date)
        vk_latency = self.calculate_latency_vk(target_date)
        
        sli_records.append((target_date, 'dm_sales_daily', 'latency_hours', sales_latency))
        sli_records.append((target_date, 'dm_vk_ads_daily', 'latency_hours', vk_latency))
        
        return sli_records
    
    def save_sli(self, sli_records: List[Tuple]):
        """Сохранение SLI в базу данных."""
        try:
            self.ch_client.insert(
                'meta.sli_daily',
                sli_records,
                column_names=['d', 'table_name', 'metric_name', 'metric_value']
            )
            logger.info(f"Сохранено {len(sli_records)} записей SLI")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения SLI: {e}")
            raise
    
    def calculate_and_save_sli(self, days: int = 3):
        """Расчет и сохранение SLI за последние дни."""
        logger.info(f"Расчет SLI за последние {days} дней")
        
        for i in range(days):
            target_date = date.today() - timedelta(days=i)
            logger.info(f"Расчет SLI для даты {target_date}")
            
            sli_records = self.calculate_all_sli(target_date)
            self.save_sli(sli_records)
        
        logger.info(f"Расчет SLI за последние {days} дней завершен")


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Расчет SLI показателей')
    parser.add_argument(
        '--days',
        type=int,
        default=3,
        help='Количество дней для расчета (по умолчанию: 3)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Конкретная дата для расчета (YYYY-MM-DD)'
    )
    
    args = parser.parse_args()
    
    try:
        calculator = SLICalculator()
        
        if args.date:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            sli_records = calculator.calculate_all_sli(target_date)
            calculator.save_sli(sli_records)
            logger.info(f"SLI для даты {target_date} рассчитаны и сохранены")
        else:
            calculator.calculate_and_save_sli(days=args.days)
        
        return 0
        
    except Exception as e:
        logger.error(f"Ошибка при расчете SLI: {e}")
        return 1


if __name__ == "__main__":
    exit(main())