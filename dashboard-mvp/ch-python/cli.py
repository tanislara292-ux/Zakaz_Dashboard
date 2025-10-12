#!/usr/bin/env python3
"""
CLI интерфейс для запуска лоадера данных из Google Sheets в ClickHouse.
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корень проекта в путь для импортов
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loader.sheets_to_ch import SheetsToClickHouseLoader
from loader.build_dm_sales import DmSalesBuilder
from loader.build_dm_vk_ads import DmVkAdsBuilder
from loader.qtickets_cdc import QTicketsCDCLoader
from loader.vk_ads_cdc import VKAdsCDCLoader
from loader.build_dm_sales_incr import DmSalesIncrementalBuilder
from loader.build_dm_vk_incr import DmVkIncrementalBuilder

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Утилиты для работы с данными в ClickHouse'
    )
    
    # Подкоманды
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда load-sheets (загрузка из Google Sheets)
    load_parser = subparsers.add_parser('load-sheets', help='Загрузка данных из Google Sheets')
    
    # Google Sheets параметры
    parser.add_argument(
        '--sheet-id',
        type=str,
        default=os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID'),
        help='ID Google Sheets таблицы'
    )
    parser.add_argument(
        '--range',
        type=str,
        default=os.getenv('GOOGLE_SHEETS_QTICKETS_RANGE', 'QTickets!A:Z'),
        help='Диапазон ячеек для чтения'
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
    
    # Параметры загрузки
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Количество дней для загрузки (по умолчанию: 7)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Размер батча для вставки (по умолчанию: 1000)'
    )
    
    # Команда build-dm-sales (построение витрины продаж)
    dm_parser = subparsers.add_parser('build-dm-sales', help='Построение материализованной витрины продаж')
    
    # Параметры дат для build-dm-sales
    dm_parser.add_argument(
        '--from',
        type=str,
        dest='from_date',
        help='Начальная дата (YYYY-MM-DD)'
    )
    dm_parser.add_argument(
        '--to',
        type=str,
        dest='to_date',
        help='Конечная дата (YYYY-MM-DD)'
    )
    dm_parser.add_argument(
        '--days',
        type=int,
        help='Количество дней от сегодняшней даты'
    )
    
    # Команда build-dm-vk (построение витрины VK Ads)
    vk_parser = subparsers.add_parser('build-dm-vk', help='Построение материализованной витрины VK Ads')
    
    # Параметры дат для build-dm-vk
    vk_parser.add_argument(
        '--from',
        type=str,
        dest='from_date',
        help='Начальная дата (YYYY-MM-DD)'
    )
    vk_parser.add_argument(
        '--to',
        type=str,
        dest='to_date',
        help='Конечная дата (YYYY-MM-DD)'
    )
    vk_parser.add_argument(
        '--days',
        type=int,
        help='Количество дней от сегодняшней даты'
    )
    
    # Команда cdc-qtickets (инкрементальная загрузка QTickets)
    cdc_qtickets_parser = subparsers.add_parser('cdc-qtickets', help='Инкрементальная загрузка QTickets CDC')
    
    # Параметры для cdc-qtickets
    cdc_qtickets_parser.add_argument(
        '--minutes',
        type=int,
        help='Интервал загрузки в минутах'
    )
    
    # Команда cdc-vk (инкрементальная загрузка VK Ads)
    cdc_vk_parser = subparsers.add_parser('cdc-vk', help='Инкрементальная загрузка VK Ads CDC')
    
    # Параметры для cdc-vk
    cdc_vk_parser.add_argument(
        '--minutes',
        type=int,
        help='Интервал загрузки в минутах'
    )
    
    # Команда build-dm-sales-incr (инкрементальное построение витрины продаж)
    dm_sales_incr_parser = subparsers.add_parser('build-dm-sales-incr', help='Инкрементальное построение витрины продаж')
    
    # Параметры для build-dm-sales-incr
    dm_sales_incr_parser.add_argument(
        '--calculate-sli',
        action='store_true',
        help='Рассчитать и обновить SLI свежести данных'
    )
    
    # Команда build-dm-vk-incr (инкрементальное построение витрины VK Ads)
    dm_vk_incr_parser = subparsers.add_parser('build-dm-vk-incr', help='Инкрементальное построение витрины VK Ads')
    
    # Параметры для build-dm-vk-incr
    dm_vk_incr_parser.add_argument(
        '--calculate-sli',
        action='store_true',
        help='Рассчитать и обновить SLI свежести данных'
    )
    
    # Общие параметры для всех команд
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробное логирование'
    )
    
    args = parser.parse_args()
    
    # Если команда не указана, показываем справку
    if not args.command:
        parser.print_help()
        return 1
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Установка общих переменных окружения из аргументов
        os.environ['CLICKHOUSE_HOST'] = args.ch_host
        os.environ['CLICKHOUSE_PORT'] = str(args.ch_port)
        os.environ['CLICKHOUSE_USER'] = args.ch_user
        os.environ['CLICKHOUSE_PASSWORD'] = args.ch_pass
        os.environ['CLICKHOUSE_DATABASE'] = args.ch_database
        
        if args.command == 'load-sheets':
            return _handle_load_sheets(args)
        elif args.command == 'build-dm-sales':
            return _handle_build_dm_sales(args)
        elif args.command == 'build-dm-vk':
            return _handle_build_dm_vk_ads(args)
        elif args.command == 'cdc-qtickets':
            return _handle_cdc_qtickets(args)
        elif args.command == 'cdc-vk':
            return _handle_cdc_vk(args)
        elif args.command == 'build-dm-sales-incr':
            return _handle_build_dm_sales_incr(args)
        elif args.command == 'build-dm-vk-incr':
            return _handle_build_dm_vk_incr(args)
        else:
            logger.error(f"Неизвестная команда: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Операция прервана пользователем")
        return 1
    except Exception as e:
        logger.error(f"Ошибка при выполнении операции: {e}")
        return 1


def _handle_load_sheets(args):
    """Обработка команды load-sheets."""
    # Проверка обязательных параметров
    if not args.sheet_id:
        logger.error("Не указан ID таблицы (--sheet-id или GOOGLE_SHEETS_SPREADSHEET_ID)")
        return 1
    
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Установка переменных окружения для Google Sheets
    os.environ['GOOGLE_SHEETS_SPREADSHEET_ID'] = args.sheet_id
    os.environ['GOOGLE_SHEETS_QTICKETS_RANGE'] = args.range
    
    # Создание и запуск лоадера
    logger.info(f"Запуск загрузки данных за последние {args.days} дней")
    loader = SheetsToClickHouseLoader()
    
    # Загрузка данных
    loader.load_qtickets_to_clickhouse(days=args.days)
    
    logger.info("Загрузка завершена успешно")
    return 0


def _handle_build_dm_sales(args):
    """Обработка команды build-dm-sales."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
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


def _handle_build_dm_vk_ads(args):
    """Обработка команды build-dm-vk."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Парсинг дат
    from_date = None
    to_date = None
    
    if args.from_date:
        from_date = datetime.strptime(args.from_date, '%Y-%m-%d').date()
    if args.to_date:
        to_date = datetime.strptime(args.to_date, '%Y-%m-%d').date()
    
    # Создание и запуск билдера
    builder = DmVkAdsBuilder()
    builder.build_dm_vk_ads(
        from_date=from_date,
        to_date=to_date,
        days=args.days
    )
    
    logger.info("Построение витрины VK Ads завершено успешно")
    return 0


def _handle_cdc_qtickets(args):
    """Обработка команды cdc-qtickets."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Создание и запуск загрузчика
    loader = QTicketsCDCLoader()
    loader.run_cdc(minutes=args.minutes)
    
    logger.info("Загрузка QTickets CDC завершена успешно")
    return 0


def _handle_cdc_vk(args):
    """Обработка команды cdc-vk."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Создание и запуск загрузчика
    loader = VKAdsCDCLoader()
    loader.run_cdc(minutes=args.minutes)
    
    logger.info("Загрузка VK Ads CDC завершена успешно")
    return 0


def _handle_build_dm_sales_incr(args):
    """Обработка команды build-dm-sales-incr."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Создание и запуск билдера
    builder = DmSalesIncrementalBuilder()
    builder.build_dm_sales_incremental()
    
    # Расчет SLI если указано
    if args.calculate_sli:
        builder.calculate_sli_freshness()
    
    logger.info("Инкрементальное построение витрины продаж завершено успешно")
    return 0


def _handle_build_dm_vk_incr(args):
    """Обработка команды build-dm-vk-incr."""
    # Проверка обязательных параметров
    if not args.ch_pass:
        logger.error("Не указан пароль ClickHouse (--ch-pass или CLICKHOUSE_PASSWORD)")
        return 1
    
    # Создание и запуск билдера
    builder = DmVkIncrementalBuilder()
    builder.build_dm_vk_incremental()
    
    # Расчет SLI если указано
    if args.calculate_sli:
        builder.calculate_sli_freshness()
    
    logger.info("Инкрементальное построение витрины VK Ads завершено успешно")
    return 0


if __name__ == "__main__":
    main()