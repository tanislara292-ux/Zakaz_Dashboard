#!/usr/bin/env python3
"""
Инкрементальный загрузчик для VK Ads CDC.
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


class VKAdsCDCLoader:
    """Класс для инкрементальной загрузки данных VK Ads."""
    
    def __init__(self):
        """Инициализация загрузчика."""
        load_dotenv()
        
        # ClickHouse настройки
        self.ch_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.ch_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.ch_user = os.getenv('CLICKHOUSE_USER', 'etl_writer')
        self.ch_password = os.getenv('CLICKHOUSE_PASSWORD')
        self.ch_database = os.getenv('CLICKHOUSE_DATABASE', 'zakaz')
        
        # VK Ads API настройки
        self.vk_access_token = os.getenv('VK_ACCESS_TOKEN')
        self.vk_account_id = os.getenv('VK_ACCOUNT_ID')
        self.vk_api_version = os.getenv('VK_API_VERSION', '5.131')
        
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
    
    def fetch_campaigns(self) -> List[Dict[str, Any]]:
        """Получение списка кампаний из VK Ads API."""
        logger.info("Загрузка списка кампаний")
        
        try:
            params = {
                'access_token': self.vk_access_token,
                'account_id': self.vk_account_id,
                'v': self.vk_api_version
            }
            
            response = self.session.get(
                'https://api.vk.com/method/ads.getCampaigns',
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"VK API Error: {data['error']}")
            
            campaigns = data.get('response', [])
            logger.info(f"Загружено {len(campaigns)} кампаний")
            return campaigns
            
        except Exception as e:
            logger.error(f"Ошибка загрузки кампаний: {e}")
            raise
    
    def fetch_ads(self, campaign_ids: List[str]) -> List[Dict[str, Any]]:
        """Получение списка объявлений из VK Ads API."""
        logger.info(f"Загрузка объявлений для {len(campaign_ids)} кампаний")
        
        all_ads = []
        
        for campaign_id in campaign_ids:
            try:
                params = {
                    'access_token': self.vk_access_token,
                    'account_id': self.vk_account_id,
                    'campaign_ids': campaign_id,
                    'v': self.vk_api_version
                }
                
                response = self.session.get(
                    'https://api.vk.com/method/ads.getAds',
                    params=params,
                    timeout=30
                )
                
                response.raise_for_status()
                data = response.json()
                
                if 'error' in data:
                    logger.warning(f"VK API Error для кампании {campaign_id}: {data['error']}")
                    continue
                
                ads = data.get('response', [])
                all_ads.extend(ads)
                
                # Небольшая задержка между запросами
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки объявлений для кампании {campaign_id}: {e}")
                continue
        
        logger.info(f"Загружено всего {len(all_ads)} объявлений")
        return all_ads
    
    def fetch_statistics(self, from_date: date, to_date: date) -> List[Dict[str, Any]]:
        """Получение статистики из VK Ads API за период."""
        logger.info(f"Загрузка статистики за период {from_date} - {to_date}")
        
        # Сначала получаем кампании и объявления
        campaigns = self.fetch_campaigns()
        campaign_ids = [str(c['id']) for c in campaigns]
        ads = self.fetch_ads(campaign_ids)
        
        # Группируем объявления по кампаниям
        ads_by_campaign = {}
        for ad in ads:
            campaign_id = str(ad['campaign_id'])
            if campaign_id not in ads_by_campaign:
                ads_by_campaign[campaign_id] = []
            ads_by_campaign[campaign_id].append(ad)
        
        all_stats = []
        
        # Получаем статистику по каждой кампании
        for campaign_id, campaign_ads in ads_by_campaign.items():
            try:
                # VK API ограничивает количество объявлений в запросе
                batch_size = 200
                ad_batches = [campaign_ads[i:i + batch_size] for i in range(0, len(campaign_ads), batch_size)]
                
                for ad_batch in ad_batches:
                    ad_ids = ','.join([str(ad['id']) for ad in ad_batch])
                    
                    params = {
                        'access_token': self.vk_access_token,
                        'account_id': self.vk_account_id,
                        'campaign_ids': campaign_id,
                        'ids': ad_ids,
                        'period': 'day',
                        'date_from': from_date.isoformat(),
                        'date_to': to_date.isoformat(),
                        'v': self.vk_api_version
                    }
                    
                    response = self.session.get(
                        'https://api.vk.com/method/ads.getStatistics',
                        params=params,
                        timeout=30
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'error' in data:
                        logger.warning(f"VK API Error для кампании {campaign_id}: {data['error']}")
                        continue
                    
                    stats = data.get('response', [])
                    all_stats.extend(stats)
                    
                    # Небольшая задержка между запросами
                    time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки статистики для кампании {campaign_id}: {e}")
                continue
        
        logger.info(f"Загружено всего {len(all_stats)} записей статистики")
        return all_stats
    
    def transform_stat(self, stat: Dict[str, Any]) -> Dict[str, Any]:
        """Трансформация записи статистики в формат стейджинга."""
        try:
            # Извлекаем необходимые поля
            stat_date = datetime.strptime(stat['day'], '%Y-%m-%d').date()
            
            # Определяем город из UTM меток или названия кампании
            city = 'unknown'
            if 'utm_content' in stat and stat['utm_content']:
                city = stat['utm_content'].lower().strip()
            elif 'link_url' in stat:
                # Пытаемся извлечь город из URL
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(stat['link_url'])
                query_params = parse_qs(parsed_url.query)
                if 'utm_content' in query_params and query_params['utm_content']:
                    city = query_params['utm_content'][0].lower().strip()
            
            campaign_id = str(stat.get('campaign_id', ''))
            ad_id = str(stat.get('id', ''))
            impressions = int(stat.get('impressions', 0))
            clicks = int(stat.get('clicks', 0))
            spend = float(stat.get('spent', 0))
            
            # Формируем запись
            now_dt = datetime.now()
            return {
                'stat_date': stat_date,
                'city': city,
                'campaign_id': campaign_id,
                'ad_id': ad_id,
                'impressions': impressions,
                'clicks': clicks,
                'spend': spend,
                
                '_src': 'vk_ads',
                '_op': 'UPSERT',
                '_ver': int(now_dt.timestamp() * 1000),
                '_loaded_at': now_dt
            }
            
        except Exception as e:
            logger.error(f"Ошибка трансформации статистики: {e}")
            raise
    
    def insert_to_staging(self, stats: List[Dict[str, Any]], batch_size: int = 5000):
        """Вставка статистики в стейджинг таблицу."""
        if not stats:
            logger.info("Нет статистики для вставки")
            return
        
        logger.info(f"Вставка {len(stats)} записей статистики в стейджинг")
        
        # Разбиваем на батчи
        for i in range(0, len(stats), batch_size):
            batch = stats[i:i + batch_size]
            
            try:
                self.ch_client.insert(
                    'zakaz.stg_vk_ads_daily',
                    batch,
                    column_names=[
                        'stat_date', 'city', 'campaign_id', 'ad_id',
                        'impressions', 'clicks', 'spend',
                        '_src', '_op', '_ver', '_loaded_at'
                    ]
                )
                
                logger.debug(f"Вставлен батч {i//batch_size + 1}, размер: {len(batch)}")
                
            except Exception as e:
                logger.error(f"Ошибка вставки батча {i//batch_size + 1}: {e}")
                raise
        
        logger.info(f"Успешно вставлено {len(stats)} записей статистики в стейджинг")
    
    def run_cdc(self, minutes: Optional[int] = None):
        """Основной метод выполнения CDC загрузки."""
        if minutes is None:
            minutes = self.nrt_interval_min
        
        # Определяем окно загрузки
        now = datetime.now()
        to_date = now.date() - timedelta(days=1)  # VK Ads имеет лаг в 1 день
        from_date = to_date - timedelta(days=self.cdc_window_days)
        
        # Получаем водяной знак
        watermark = self.get_watermark('vk_ads', 'ads_daily', 'date')
        if watermark:
            try:
                watermark_date = datetime.strptime(watermark, '%Y-%m-%d').date()
                from_date = max(from_date, watermark_date)
            except ValueError:
                logger.warning(f"Неверный формат водяного знака: {watermark}, используем по умолчанию")
        
        logger.info(f"Окно загрузки: {from_date} - {to_date}")
        
        try:
            # Шаг 1: Загрузка данных из источника
            stats = self.fetch_statistics(from_date, to_date)
            
            # Шаг 2: Трансформация данных
            transformed_stats = [self.transform_stat(stat) for stat in stats]
            
            # Шаг 3: Вставка в стейджинг
            self.insert_to_staging(transformed_stats)
            
            # Шаг 4: Обновление водяного знака
            # Используем to_date - 1 день чтобы оставить перекрытие
            new_watermark = (to_date - timedelta(days=1)).isoformat()
            self.update_watermark('vk_ads', 'ads_daily', 'date', new_watermark)
            
            logger.info(f"CDC загрузка завершена успешно. Обработано записей: {len(transformed_stats)}")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении CDC загрузки: {e}")
            raise


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Инкрементальная загрузка VK Ads CDC'
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
    
    if not args.vk_access_token or not args.vk_account_id:
        logger.error("Не указаны VK_ACCESS_TOKEN или VK_ACCOUNT_ID")
        return 1
    
    try:
        # Установка переменных окружения из аргументов
        os.environ['CLICKHOUSE_HOST'] = args.ch_host
        os.environ['CLICKHOUSE_PORT'] = str(args.ch_port)
        os.environ['CLICKHOUSE_USER'] = args.ch_user
        os.environ['CLICKHOUSE_PASSWORD'] = args.ch_pass
        os.environ['CLICKHOUSE_DATABASE'] = args.ch_database
        
        # Создание и запуск загрузчика
        loader = VKAdsCDCLoader()
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