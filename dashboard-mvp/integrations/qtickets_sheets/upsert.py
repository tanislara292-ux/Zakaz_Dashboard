"""
Модуль для записи данных в ClickHouse с поддержкой upsert и дедупликации.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Настройка логгера
logger = logging.getLogger(__name__)

class ClickHouseUpsert:
    """Класс для выполнения upsert операций в ClickHouse."""
    
    def __init__(self, ch_client):
        """
        Инициализация upsert клиента.
        
        Args:
            ch_client: Клиент ClickHouse
        """
        self.ch_client = ch_client
    
    def insert_raw_data(self, data: List[Dict[str, Any]], source: str, 
                       sheet_id: str, tab: str) -> int:
        """
        Вставка сырых данных в стейджинг таблицу.
        
        Args:
            data: Данные для вставки
            source: Источник данных
            sheet_id: ID таблицы Google Sheets
            tab: Имя листа
            
        Returns:
            Количество вставленных строк
        """
        if not data:
            logger.warning("Нет данных для вставки в стейджинг")
            return 0
        
        try:
            # Подготовка данных для вставки
            now = datetime.now()
            processed_data = []
            
            for row in data:
                processed_row = {
                    'source': source,
                    'sheet_id': sheet_id,
                    'tab': tab,
                    'payload_json': json.dumps(row, ensure_ascii=False),
                    '_ver': int(now.timestamp()),
                    '_ingest_ts': now,
                    'hash_low_card': row.get('hash_low_card', '')
                }
                processed_data.append(processed_row)
            
            # Вставка данных
            self.ch_client.insert('zakaz.stg_qtickets_sheets_raw', processed_data)
            
            logger.info(f"Вставлено {len(processed_data)} строк в стейджинг таблицу")
            return len(processed_data)
            
        except Exception as e:
            logger.error(f"Ошибка при вставке данных в стейджинг: {e}")
            raise
    
    def upsert_events(self, data: List[Dict[str, Any]]) -> int:
        """
        Upsert данных мероприятий в таблицу dim_events.
        
        Args:
            data: Данные мероприятий
            
        Returns:
            Количество обработанных строк
        """
        if not data:
            logger.warning("Нет данных для upsert в dim_events")
            return 0
        
        try:
            # Вставка в стейджинг с последующим мержем
            self.ch_client.insert('zakaz.stg_qtickets_sheets_events', data)
            
            # Выполнение мержа в основную таблицу
            merge_query = """
            INSERT INTO zakaz.dim_events
            SELECT 
                event_id,
                event_name,
                event_date,
                city,
                tickets_total,
                tickets_left,
                _ver
            FROM (
                SELECT 
                    *,
                    row_number() OVER (PARTITION BY event_id ORDER BY _ver DESC) as rn
                FROM zakaz.stg_qtickets_sheets_events
            )
            WHERE rn = 1
            """
            
            self.ch_client.execute(merge_query)
            
            logger.info(f"Upsert выполнен для {len(data)} мероприятий")
            return len(data)
            
        except Exception as e:
            logger.error(f"Ошибка при upsert мероприятий: {e}")
            raise
    
    def upsert_inventory(self, data: List[Dict[str, Any]]) -> int:
        """
        Upsert данных инвентаря в таблицу fact_qtickets_inventory.
        
        Args:
            data: Данные инвентаря
            
        Returns:
            Количество обработанных строк
        """
        if not data:
            logger.warning("Нет данных для upsert в fact_qtickets_inventory")
            return 0
        
        try:
            # Вставка в стейджинг
            self.ch_client.insert('zakaz.stg_qtickets_sheets_inventory', data)
            
            # Выполнение мержа в основную таблицу
            merge_query = """
            INSERT INTO zakaz.fact_qtickets_inventory
            SELECT 
                event_id,
                city,
                tickets_total,
                tickets_left,
                _ver
            FROM (
                SELECT 
                    *,
                    row_number() OVER (PARTITION BY event_id, city ORDER BY _ver DESC) as rn
                FROM zakaz.stg_qtickets_sheets_inventory
            )
            WHERE rn = 1
            """
            
            self.ch_client.execute(merge_query)
            
            logger.info(f"Upsert выполнен для {len(data)} записей инвентаря")
            return len(data)
            
        except Exception as e:
            logger.error(f"Ошибка при upsert инвентаря: {e}")
            raise
    
    def upsert_sales(self, data: List[Dict[str, Any]]) -> int:
        """
        Upsert данных продаж в таблицу fact_qtickets_sales.
        
        Args:
            data: Данные продаж
            
        Returns:
            Количество обработанных строк
        """
        if not data:
            logger.warning("Нет данных для upsert в fact_qtickets_sales")
            return 0
        
        try:
            # Вставка в стейджинг
            self.ch_client.insert('zakaz.stg_qtickets_sheets_sales', data)
            
            # Выполнение мержа в основную таблицу
            merge_query = """
            INSERT INTO zakaz.fact_qtickets_sales
            SELECT 
                date,
                event_id,
                event_name,
                city,
                tickets_sold,
                revenue,
                refunds,
                currency,
                _ver
            FROM (
                SELECT 
                    *,
                    row_number() OVER (PARTITION BY date, event_id, city ORDER BY _ver DESC) as rn
                FROM zakaz.stg_qtickets_sheets_sales
            )
            WHERE rn = 1
            """
            
            self.ch_client.execute(merge_query)
            
            logger.info(f"Upsert выполнен для {len(data)} записей продаж")
            return len(data)
            
        except Exception as e:
            logger.error(f"Ошибка при upsert продаж: {e}")
            raise
    
    def check_existing_hashes(self, hashes: List[str], table: str) -> set:
        """
        Проверка существующих хэшей в таблице.
        
        Args:
            hashes: Список хэшей для проверки
            table: Имя таблицы
            
        Returns:
            Множество существующих хэшей
        """
        if not hashes:
            return set()
        
        try:
            query = f"""
            SELECT DISTINCT hash_low_card
            FROM {table}
            WHERE hash_low_card IN ({','.join([f"'{h}'" for h in hashes])})
            """
            
            result = self.ch_client.execute(query)
            existing_hashes = set()
            
            if result and result.first_row:
                for row in result.first_row:
                    existing_hashes.add(row['hash_low_card'])
            
            logger.info(f"Найдено {len(existing_hashes)} существующих хэшей в таблице {table}")
            return existing_hashes
            
        except Exception as e:
            logger.error(f"Ошибка при проверке существующих хэшей: {e}")
            return set()
    
    def filter_new_data(self, data: List[Dict[str, Any]], table: str) -> List[Dict[str, Any]]:
        """
        Фильтрация данных, отсеивая уже существующие записи.
        
        Args:
            data: Данные для фильтрации
            table: Имя таблицы для проверки
            
        Returns:
            Отфильтрованные данные
        """
        if not data:
            return []
        
        # Извлечение хэшей
        hashes = [row.get('hash_low_card', '') for row in data]
        existing_hashes = self.check_existing_hashes(hashes, table)
        
        # Фильтрация
        new_data = [row for row in data if row.get('hash_low_card', '') not in existing_hashes]
        
        logger.info(f"Отфильтровано {len(new_data)} новых записей из {len(data)}")
        return new_data
    
    def record_job_run(self, job: str, status: str, rows_processed: int = 0, 
                      message: str = "", metrics: Dict[str, Any] = None) -> None:
        """
        Запись информации о запуске задачи.
        
        Args:
            job: Название задачи
            status: Статус (success, error, running)
            rows_processed: Количество обработанных строк
            message: Сообщение
            metrics: Метрики
        """
        try:
            run_data = {
                'job': job,
                'started_at': datetime.now(),
                'finished_at': datetime.now(),
                'rows_processed': rows_processed,
                'status': status,
                'message': message,
                'metrics': json.dumps(metrics or {})
            }
            
            self.ch_client.insert('zakaz.meta_job_runs', [run_data])
            
        except Exception as e:
            logger.error(f"Ошибка при записи информации о запуске задачи: {e}")
    
    def cleanup_staging_tables(self, days_to_keep: int = 30) -> None:
        """
        Очистка стейджинг таблиц от старых данных.
        
        Args:
            days_to_keep: Количество дней для хранения данных
        """
        try:
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
            
            tables_to_clean = [
                'zakaz.stg_qtickets_sheets_raw',
                'zakaz.stg_qtickets_sheets_events',
                'zakaz.stg_qtickets_sheets_inventory',
                'zakaz.stg_qtickets_sheets_sales'
            ]
            
            for table in tables_to_clean:
                delete_query = f"""
                ALTER TABLE {table}
                DELETE WHERE _ingest_ts < '{cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}'
                """
                
                self.ch_client.execute(delete_query)
                logger.info(f"Очищена таблица {table} от данных старше {days_to_keep} дней")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке стейджинг таблиц: {e}")