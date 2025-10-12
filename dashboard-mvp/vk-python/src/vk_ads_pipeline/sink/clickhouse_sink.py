"""ClickHouse sink for VK Ads data."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import List, Dict, Any

import clickhouse_connect
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ClickHouseSink:
    """Класс для загрузки данных VK Ads в ClickHouse."""
    
    def __init__(self):
        """Инициализация sink."""
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
    
    def _generate_dedup_key(self, row: Dict[str, Any]) -> int:
        """Генерация дедуп ключа на основе хеша."""
        import hashlib
        
        # Создаем строку для хеширования из ключевых полей
        key_string = f"{row.get('stat_date', '')}|{row.get('account_id', '')}|{row.get('campaign_id', '')}|{row.get('ad_id', '')}|{row.get('utm_source', '')}|{row.get('utm_medium', '')}|{row.get('utm_campaign', '')}|{row.get('utm_content', '')}|{row.get('utm_term', '')}"
        
        # Возвращаем хеш как число
        return int(hashlib.md5(key_string.encode()).hexdigest()[:16], 16)
    
    def insert_vk_stg(self, rows: List[Dict[str, Any]], batch_size: int = 1000):
        """Вставка данных в stg_vk_ads_daily."""
        if not rows:
            logger.warning("Нет данных для вставки")
            return
        
        try:
            # Подготовка данных для вставки
            rows_to_insert = []
            for row in rows:
                # Конвертация spend в копейки
                spend_copies = 0
                try:
                    spend_value = float(row.get('cost', 0))
                    spend_copies = int(spend_value * 100)  # Конвертация в копейки
                except (ValueError, TypeError):
                    logger.warning(f"Некорректное значение spend: {row.get('cost')}")
                
                # Генерация dedup ключа
                dedup_key = self._generate_dedup_key(row)
                
                rows_to_insert.append([
                    row.get('date'),                    # stat_date
                    int(row.get('account_id', 0)),     # account_id
                    int(row.get('campaign_id', 0)),    # campaign_id
                    int(row.get('adgroup_id', 0)),     # ad_id
                    row.get('utm_source', ''),         # utm_source
                    row.get('utm_medium', ''),         # utm_medium
                    row.get('utm_campaign', ''),       # utm_campaign
                    row.get('utm_content', ''),        # utm_content
                    row.get('utm_term', ''),           # utm_term
                    int(row.get('impressions', 0)),    # impressions
                    int(row.get('clicks', 0)),         # clicks
                    spend_copies,                      # spend (в копейках)
                    row.get('currency', 'RUB'),        # currency
                    row.get('city', ''),               # city_raw
                    dedup_key,                         # _dedup_key
                    int(hashlib.md5(f"{dedup_key}_{row.get('date')}".encode()).hexdigest()[:16], 16)  # _ver
                ])
            
            # Вставка батчами
            total_inserted = 0
            for i in range(0, len(rows_to_insert), batch_size):
                batch = rows_to_insert[i:i + batch_size]
                self.ch_client.insert(
                    'stg_vk_ads_daily',
                    batch,
                    column_names=[
                        'stat_date', 'account_id', 'campaign_id', 'ad_id',
                        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
                        'impressions', 'clicks', 'spend', 'currency', 'city_raw', '_dedup_key', '_ver'
                    ]
                )
                total_inserted += len(batch)
                logger.info(f"Вставлено {len(batch)} строк в stg_vk_ads_daily (всего: {total_inserted})")
            
            logger.info(f"Успешно вставлено {total_inserted} строк в stg_vk_ads_daily")
            return total_inserted
            
        except Exception as e:
            logger.error(f"Ошибка вставки данных в ClickHouse: {e}")
            raise