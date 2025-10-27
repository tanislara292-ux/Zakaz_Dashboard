"""
QTickets Google Sheets загрузчик.
Загружает данные о мероприятиях, инвентаре и продажах из Google Sheets.
"""

import os
import sys
import argparse
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, today_msk, to_date, days_ago,
    setup_integrations_logger, log_data_operation
)
from integrations.qtickets_sheets.gsheets_client import GoogleSheetsClient
from integrations.qtickets_sheets.transform import DataTransformer
from integrations.qtickets_sheets.upsert import ClickHouseUpsert

# Настройка логгера
logger = setup_integrations_logger('qtickets_sheets')

class QTicketsSheetsLoader:
    """Загрузчик данных QTickets из Google Sheets в ClickHouse."""
    
    def __init__(self, ch_client: ClickHouseClient, gsheets_client: GoogleSheetsClient,
                 transformer: DataTransformer, upserter: ClickHouseUpsert):
        """
        Инициализация загрузчика.
        
        Args:
            ch_client: Клиент ClickHouse
            gsheets_client: Клиент Google Sheets
            transformer: Трансформер данных
            upserter: Upsert клиент ClickHouse
        """
        self.ch_client = ch_client
        self.gsheets_client = gsheets_client
        self.transformer = transformer
        self.upserter = upserter
        
        # Конфигурация из переменных окружения
        self.sheet_ids = {
            'sales': os.getenv('SHEET_ID_SALES'),
            'events': os.getenv('SHEET_ID_EVENTS'),
            'inventory': os.getenv('SHEET_ID_INVENTORY')
        }
        
        self.tab_names = {
            'sales': os.getenv('TAB_SALES', 'Sales'),
            'events': os.getenv('TAB_EVENTS', 'Events'),
            'inventory': os.getenv('TAB_INVENTORY', 'Inventory')
        }
        
        self.required_headers = {
            'sales': ['date', 'event_id', 'city', 'tickets_sold', 'revenue'],
            'events': ['event_id', 'event_name', 'event_date', 'city'],
            'inventory': ['event_id', 'city']
        }
    
    @log_data_operation(logger, 'load', 'google_sheets', 'clickhouse')
    def load_events(self) -> int:
        """
        Загрузка мероприятий в ClickHouse.
        
        Returns:
            Количество загруженных мероприятий
        """
        logger.info("Начало загрузки мероприятий")
        
        try:
            sheet_id = self.sheet_ids['events']
            tab_name = self.tab_names['events']
            
            if not sheet_id:
                logger.warning("Не указан SHEET_ID_EVENTS, пропуск загрузки мероприятий")
                return 0
            
            # Проверка заголовков
            if not self.gsheets_client.validate_headers(
                sheet_id, tab_name, self.required_headers['events']
            ):
                raise ValueError(f"Некорректные заголовки в листе {tab_name}")
            
            # Чтение данных
            raw_data = self.gsheets_client.read_sheet_all(sheet_id, tab_name)
            
            if not raw_data:
                logger.warning("Нет данных о мероприятиях для загрузки")
                return 0
            
            # Трансформация данных
            transformed_data = self.transformer.transform_events(raw_data)
            
            if not transformed_data:
                logger.warning("Нет корректных данных о мероприятиях после трансформации")
                return 0
            
            # Upsert в ClickHouse
            self.upserter.upsert_events(transformed_data)
            
            logger.info(f"Загружено {len(transformed_data)} мероприятий")
            return len(transformed_data)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке мероприятий: {e}")
            raise
    
    @log_data_operation(logger, 'load', 'google_sheets', 'clickhouse')
    def load_inventory(self) -> int:
        """
        Загрузка инвентаря в ClickHouse.
        
        Returns:
            Количество загруженных записей инвентаря
        """
        logger.info("Начало загрузки инвентаря")
        
        try:
            sheet_id = self.sheet_ids['inventory']
            tab_name = self.tab_names['inventory']
            
            if not sheet_id:
                logger.warning("Не указан SHEET_ID_INVENTORY, пропуск загрузки инвентаря")
                return 0
            
            # Проверка заголовков
            if not self.gsheets_client.validate_headers(
                sheet_id, tab_name, self.required_headers['inventory']
            ):
                raise ValueError(f"Некорректные заголовки в листе {tab_name}")
            
            # Чтение данных
            raw_data = self.gsheets_client.read_sheet_all(sheet_id, tab_name)
            
            if not raw_data:
                logger.warning("Нет данных об инвентаре для загрузки")
                return 0
            
            # Трансформация данных
            transformed_data = self.transformer.transform_inventory(raw_data)
            
            if not transformed_data:
                logger.warning("Нет корректных данных об инвентаре после трансформации")
                return 0
            
            # Upsert в ClickHouse
            self.upserter.upsert_inventory(transformed_data)
            
            logger.info(f"Загружено {len(transformed_data)} записей инвентаря")
            return len(transformed_data)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке инвентаря: {e}")
            raise
    
    @log_data_operation(logger, 'load', 'google_sheets', 'clickhouse')
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
            sheet_id = self.sheet_ids['sales']
            tab_name = self.tab_names['sales']
            
            if not sheet_id:
                logger.warning("Не указан SHEET_ID_SALES, пропуск загрузки продаж")
                return 0
            
            # Проверка заголовков
            if not self.gsheets_client.validate_headers(
                sheet_id, tab_name, self.required_headers['sales']
            ):
                raise ValueError(f"Некорректные заголовки в листе {tab_name}")
            
            # Чтение данных
            raw_data = self.gsheets_client.read_sheet_all(sheet_id, tab_name)
            
            if not raw_data:
                logger.warning("Нет данных о продажах для загрузки")
                return 0
            
            # Трансформация данных
            transformed_data = self.transformer.transform_sales(raw_data)
            
            if not transformed_data:
                logger.warning("Нет корректных данных о продажах после трансформации")
                return 0
            
            # Фильтрация по дате, если указаны границы
            if date_from or date_to:
                filtered_data = []
                for row in transformed_data:
                    row_date = row.get('date')
                    if row_date:
                        if date_from and row_date < date_from:
                            continue
                        if date_to and row_date > date_to:
                            continue
                    filtered_data.append(row)
                transformed_data = filtered_data
            
            # Upsert в ClickHouse
            self.upserter.upsert_sales(transformed_data)
            
            logger.info(f"Загружено {len(transformed_data)} записей о продажах")
            return len(transformed_data)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке продаж: {e}")
            raise
    
    def load_all(self, date_from: date = None, date_to: date = None, 
                dry_run: bool = False) -> Dict[str, int]:
        """
        Полная загрузка данных (мероприятия, инвентарь и продажи).
        
        Args:
            date_from: Начальная дата для продаж
            date_to: Конечная дата для продаж
            dry_run: Тестовый режим без записи в ClickHouse
            
        Returns:
            Словарь с количеством загруженных записей
        """
        logger.info("Начало полной загрузки данных QTickets из Google Sheets")
        
        if dry_run:
            logger.info("ТЕСТОВЫЙ РЕЖИМ: данные не будут записаны в ClickHouse")
        
        results = {}
        
        # Загрузка мероприятий
        try:
            if not dry_run:
                results['events'] = self.load_events()
            else:
                # В тестовом режиме только проверяем доступность данных
                sheet_id = self.sheet_ids['events']
                if sheet_id and self.gsheets_client.validate_headers(
                    sheet_id, self.tab_names['events'], self.required_headers['events']
                ):
                    raw_data = self.gsheets_client.read_sheet_all(sheet_id, self.tab_names['events'])
                    transformed_data = self.transformer.transform_events(raw_data)
                    results['events'] = len(transformed_data)
                else:
                    results['events'] = 0
        except Exception as e:
            logger.error(f"Ошибка при загрузке мероприятий: {e}")
            results['events'] = 0
        
        # Загрузка инвентаря
        try:
            if not dry_run:
                results['inventory'] = self.load_inventory()
            else:
                # В тестовом режиме только проверяем доступность данных
                sheet_id = self.sheet_ids['inventory']
                if sheet_id and self.gsheets_client.validate_headers(
                    sheet_id, self.tab_names['inventory'], self.required_headers['inventory']
                ):
                    raw_data = self.gsheets_client.read_sheet_all(sheet_id, self.tab_names['inventory'])
                    transformed_data = self.transformer.transform_inventory(raw_data)
                    results['inventory'] = len(transformed_data)
                else:
                    results['inventory'] = 0
        except Exception as e:
            logger.error(f"Ошибка при загрузке инвентаря: {e}")
            results['inventory'] = 0
        
        # Загрузка продаж
        try:
            if not dry_run:
                results['sales'] = self.load_sales(date_from, date_to)
            else:
                # В тестовом режиме только проверяем доступность данных
                sheet_id = self.sheet_ids['sales']
                if sheet_id and self.gsheets_client.validate_headers(
                    sheet_id, self.tab_names['sales'], self.required_headers['sales']
                ):
                    raw_data = self.gsheets_client.read_sheet_all(sheet_id, self.tab_names['sales'])
                    transformed_data = self.transformer.transform_sales(raw_data)
                    results['sales'] = len(transformed_data)
                else:
                    results['sales'] = 0
        except Exception as e:
            logger.error(f"Ошибка при загрузке продаж: {e}")
            results['sales'] = 0
        
        logger.info(f"Загрузка завершена: {results}")
        return results

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='QTickets Google Sheets загрузчик')
    parser.add_argument('--envfile', type=str, default='secrets/.env.qtickets_sheets', 
                       help='Путь к файлу с переменными окружения')
    parser.add_argument('--ch-env', type=str, default='secrets/.env.ch', 
                       help='Путь к файлу с переменными окружения ClickHouse')
    parser.add_argument('--since', type=str, help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--to', type=str, help='Конечная дата в формате YYYY-MM-DD')
    parser.add_argument('--days', type=int, help='Количество дней для загрузки')
    parser.add_argument('--dry-run', action='store_true', help='Тестовый режим без записи в ClickHouse')
    parser.add_argument('--verbose', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.envfile)
    load_dotenv(args.ch_env)
    
    # Настройка уровня логирования
    if args.verbose:
        os.environ['LOG_LEVEL'] = 'DEBUG'
    
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
        ch_client = get_client(args.ch_env)
        gsheets_client = GoogleSheetsClient()
        transformer = DataTransformer()
        upserter = ClickHouseUpsert(ch_client)
        
        loader = QTicketsSheetsLoader(ch_client, gsheets_client, transformer, upserter)
        
        # Запись о начале работы
        if not args.dry_run:
            upserter.record_job_run('qtickets_sheets', 'running')
        
        # Загрузка данных
        results = loader.load_all(date_from, date_to, args.dry_run)
        
        # Запись об успешном завершении
        if not args.dry_run:
            total_rows = sum(results.values())
            upserter.record_job_run(
                'qtickets_sheets', 'success', 
                total_rows, f"Загружено: {results}", results
            )
        
        logger.info(f"Загрузка успешно завершена: {results}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении загрузчика: {e}")
        
        # Попытка записи об ошибке
        try:
            ch_client = get_client(args.ch_env)
            upserter = ClickHouseUpsert(ch_client)
            upserter.record_job_run('qtickets_sheets', 'error', 0, str(e))
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main()