#!/usr/bin/env python3
"""
Инкрементальный билдер витрины VK Ads dm_vk_ads_daily.
"""
import os
import logging
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, List

import clickhouse_connect
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DmVkIncrementalBuilder:
    """Класс для инкрементального построения витрины VK Ads."""
    
    def __init__(self):
        """Инициализация билдера."""
        load_dotenv()
        
        # ClickHouse настройки
        self.ch_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.ch_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.ch_user = os.getenv('CLICKHOUSE_USER', 'etl_writer')
        self.ch_password = os.getenv('CLICKHOUSE_PASSWORD')
        self.ch_database = os.getenv('CLICKHOUSE_DATABASE', 'zakaz')
        
        # NRT настройки
        self.cdc_window_days = int(os.getenv('CDC_WINDOW_DAYS', '3'))
        
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
    
    def get_affected_dates(self) -> List[date]:
        """Определение затронутых дат на основе данных в стейджинге."""
        try:
            query = """
            SELECT DISTINCT stat_date
            FROM zakaz.stg_vk_ads_daily
            WHERE stat_date >= today() - %(days)s
            ORDER BY stat_date
            """
            
            result = self.ch_client.query(
                query,
                parameters={
                    'days': self.cdc_window_days
                }
            )
            
            dates = [row[0] for row in result.result_rows]
            logger.info(f"Найдено {len(dates)} затронутых дат: {dates}")
            return dates
            
        except Exception as e:
            logger.error(f"Ошибка определения затронутых дат: {e}")
            raise
    
    def rebuild_date_partition(self, target_date: date):
        """Пересборка партиции за конкретную дату."""
        logger.info(f"Пересборка партиции VK Ads за дату {target_date}")
        
        try:
            # Шаг 1: Определение активных ключей (последний оп - UPSERT)
            active_keys_sql = """
            WITH last_ops AS (
              SELECT stat_date, city, campaign_id, ad_id,
                     argMax(_op, _ver) AS last_op
              FROM zakaz.stg_vk_ads_daily
              WHERE stat_date = %(target_date)s
              GROUP BY stat_date, city, campaign_id, ad_id
            )
            SELECT stat_date, city, campaign_id, ad_id
            FROM last_ops 
            WHERE last_op = 'UPSERT'
            """
            
            # Временная таблица с активными ключами
            temp_table = f"temp_vk_active_keys_{int(target_date.strftime('%Y%m%d'))}"
            
            self.ch_client.command(f"""
                CREATE TEMPORARY TABLE {temp_table} (
                    stat_date Date,
                    city String,
                    campaign_id String,
                    ad_id String
                ) ENGINE = Memory
            """)
            
            self.ch_client.command(f"""
                INSERT INTO {temp_table}
                {active_keys_sql}
            """, parameters={'target_date': target_date})
            
            # Шаг 2: Удаление существующих данных за дату
            delete_sql = """
            ALTER TABLE zakaz.dm_vk_ads_daily DELETE 
            WHERE stat_date = %(target_date)s
            """
            
            self.ch_client.command(
                delete_sql,
                parameters={'target_date': target_date}
            )
            
            # Шаг 3: Вставка новых данных с учетом только активных ключей
            insert_sql = f"""
            INSERT INTO zakaz.dm_vk_ads_daily
            SELECT
                s.stat_date,
                coalesce(a.city, lowerUTF8(trim(BOTH ' ' FROM s.city))) AS city,
                sum(s.impressions) AS impressions,
                sum(s.clicks)      AS clicks,
                toUInt64(sum(s.spend) * 100) AS spend,
                max(s._ver)        AS _ver
            FROM zakaz.stg_vk_ads_daily AS s
            INNER JOIN {temp_table} AS k
              ON s.stat_date = k.stat_date
             AND s.city = k.city
             AND s.campaign_id = k.campaign_id
             AND s.ad_id = k.ad_id
            LEFT JOIN zakaz.dim_city_alias AS a
              ON lowerUTF8(a.alias) = lowerUTF8(s.city)
            WHERE s.stat_date = %(target_date)s
              AND s._op = 'UPSERT'
            GROUP BY s.stat_date, city
            """
            
            result = self.ch_client.command(
                insert_sql,
                parameters={'target_date': target_date}
            )
            
            logger.info(f"Пересборка партиции VK Ads за {target_date} завершена. Обработано строк: {result}")
            
        except Exception as e:
            logger.error(f"Ошибка пересборки партиции VK Ads за {target_date}: {e}")
            raise
    
    def build_dm_vk_incremental(self):
        """Основной метод инкрементального построения витрины."""
        logger.info("Запуск инкрементального построения витрины dm_vk_ads_daily")
        
        try:
            # Шаг 1: Определение затронутых дат
            affected_dates = self.get_affected_dates()
            
            if not affected_dates:
                logger.info("Нет затронутых дат для обработки")
                return
            
            # Шаг 2: Пересборка партиций для каждой даты
            for target_date in affected_dates:
                self.rebuild_date_partition(target_date)
            
            logger.info(f"Инкрементальное построение витрины VK Ads завершено. Обработано дат: {len(affected_dates)}")
            
        except Exception as e:
            logger.error(f"Ошибка при инкрементальном построении витрины VK Ads: {e}")
            raise
    
    def calculate_sli_freshness(self):
        """Расчет SLI для свежести данных."""
        try:
            now = datetime.now()
            
            # Для сегодняшней даты
            today_freshness_hours = 0
            today_data = self.ch_client.query("""
                SELECT max(_loaded_at) AS max_loaded_at
                FROM zakaz.dm_vk_ads_daily
                WHERE stat_date = today()
            """).result_rows
            
            if today_data and today_data[0][0]:
                max_loaded_at = today_data[0][0]
                freshness_hours = (now - max_loaded_at).total_seconds() / 3600
                today_freshness = max(0, freshness_hours)
            
            # Для вчерашней даты
            yesterday_freshness_hours = 0
            yesterday_data = self.ch_client.query("""
                SELECT max(_loaded_at) AS max_loaded_at
                FROM zakaz.dm_vk_ads_daily
                WHERE stat_date = yesterday()
            """).result_rows
            
            if yesterday_data and yesterday_data[0][0]:
                max_loaded_at = yesterday_data[0][0]
                freshness_hours = (now - max_loaded_at).total_seconds() / 3600
                yesterday_freshness = max(0, freshness_hours)
            
            # Запись SLI в таблицу
            sli_records = [
                (date.today(), 'dm_vk_ads_daily', 'freshness_hours_today', today_freshness),
                (date.today() - timedelta(days=1), 'dm_vk_ads_daily', 'freshness_hours_yesterday', yesterday_freshness)
            ]
            
            self.ch_client.insert(
                'meta.sli_daily',
                sli_records,
                column_names=['d', 'table_name', 'metric_name', 'metric_value']
            )
            
            logger.info(f"SLI свежести VK Ads обновлен: сегодня={today_freshness:.2f}ч, вчера={yesterday_freshness:.2f}ч")
            
        except Exception as e:
            logger.error(f"Ошибка расчета SLI свежести VK Ads: {e}")
            raise


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Инкрементальное построение витрины VK Ads dm_vk_ads_daily'
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
    parser.add_argument(
        '--calculate-sli',
        action='store_true',
        help='Рассчитать и обновить SLI свежести данных'
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
        
        # Создание и запуск билдера
        builder = DmVkIncrementalBuilder()
        builder.build_dm_vk_incremental()
        
        # Расчет SLI если указано
        if args.calculate_sli:
            builder.calculate_sli_freshness()
        
        logger.info("Инкрементальное построение витрины VK Ads завершено успешно")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Построение прервано пользователем")
        return 1
    except Exception as e:
        logger.error(f"Ошибка при построении витрины VK Ads: {e}")
        return 1


if __name__ == "__main__":
    exit(main())