"""
VK Ads API загрузчик.
Загружает статистику по рекламным кампаниям VK Ads в ClickHouse.
"""

import os
import sys
import argparse
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Iterable
from urllib.parse import parse_qs, urlparse

import httpx

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, today_msk, to_date, days_ago,
    setup_integrations_logger, log_data_operation,
    parse_utm_content, extract_utm_params
)

# Настройка логгера
logger = setup_integrations_logger('vk_ads')

class VkAdsError(RuntimeError):
    """Базовый класс ошибок VK Ads API."""

class VkAdsClient:
    """Клиент для работы с VK Ads API."""
    
    def __init__(
        self,
        access_token: str,
        api_version: str = "5.131",
        timeout: float = 30.0,
        base_url: str = "https://api.vk.com",
    ):
        """
        Инициализация клиента VK Ads API.
        
        Args:
            access_token: токен доступа
            api_version: версия API
            timeout: таймаут запросов
            base_url: базовый URL API
        """
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._token = access_token
        self._version = api_version
    
    def close(self):
        """Закрытие клиента."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.close()
    
    def _request(self, method: str, params: dict) -> dict:
        """
        Выполнение запроса к API.
        
        Args:
            method: метод API
            params: параметры запроса
            
        Returns:
            Ответ API
        """
        payload = dict(params)
        payload["access_token"] = self._token
        payload["v"] = self._version
        
        try:
            response = self._client.post(f"/method/{method}", data=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise VkAdsError(f"Ошибка запроса к VK API: {e}")
        
        if "error" in data:
            err = data["error"]
            raise VkAdsError(
                f"VK API error {err.get('error_code')}: {err.get('error_msg')} (method={method})"
            )
        
        return data.get("response", {})
    
    def get_campaigns(
        self,
        account_id: int,
        client_id: int = None,
        campaign_ids: List[int] = None,
    ) -> List[Dict]:
        """
        Получение списка кампаний.
        
        Args:
            account_id: ID аккаунта
            client_id: ID клиента (для агентских аккаунтов)
            campaign_ids: список ID кампаний
            
        Returns:
            Список кампаний
        """
        params = {"account_id": account_id}
        if client_id is not None:
            params["client_id"] = client_id
        if campaign_ids:
            params["campaign_ids"] = json.dumps([{"campaign_id": cid} for cid in campaign_ids])
        
        result = self._request("ads.getCampaigns", params)
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return result if isinstance(result, list) else []
    
    def get_ads(
        self,
        account_id: int,
        campaign_ids: List[int],
        client_id: int = None,
        include_deleted: bool = False,
    ) -> List[Dict]:
        """
        Получение списка объявлений.
        
        Args:
            account_id: ID аккаунта
            campaign_ids: список ID кампаний
            client_id: ID клиента (для агентских аккаунтов)
            include_deleted: включать удаленные
            
        Returns:
            Список объявлений
        """
        params = {
            "account_id": account_id,
            "include_deleted": 1 if include_deleted else 0,
            "campaign_ids": json.dumps([{"campaign_id": cid} for cid in campaign_ids]),
        }
        if client_id is not None:
            params["client_id"] = client_id
        
        result = self._request("ads.getAds", params)
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return result if isinstance(result, list) else []
    
    def get_statistics(
        self,
        account_id: int,
        ids_type: str,
        ids: List[int],
        period: str,
        date_from: str,
        date_to: str,
        metrics: Iterable[str],
        client_id: int = None,
    ) -> List[Dict]:
        """
        Получение статистики.
        
        Args:
            account_id: ID аккаунта
            ids_type: тип ID (campaign, ad, ad_group)
            ids: список ID
            period: период (day, week, month, overall)
            date_from: начальная дата
            date_to: конечная дата
            metrics: метрики
            client_id: ID клиента (для агентских аккаунтов)
            
        Returns:
            Статистика
        """
        params = {
            "account_id": account_id,
            "ids_type": ids_type,
            "ids": ",".join(str(item) for item in ids),
            "period": period,
            "date_from": date_from,
            "date_to": date_to,
            "metrics": ",".join(metrics),
        }
        if client_id is not None:
            params["client_id"] = client_id
        
        result = self._request("ads.getStatistics", params)
        return result if isinstance(result, list) else []

def _chunked(values: Iterable[int], size: int):
    """Разбивает значения на чанки."""
    chunk = []
    for value in values:
        chunk.append(value)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

def parse_utm_from_url(url: str) -> Dict[str, str]:
    """
    Парсит UTM-метки из URL.
    
    Args:
        url: URL
        
    Returns:
        Словарь с UTM-метками
    """
    if not url:
        return {}
    
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return {key: values[0] for key, values in params.items() 
                if key.startswith("utm_") and values}
    except Exception:
        return {}

def normalize_vk_ads_row(row: Dict[str, Any], account_id: int) -> Dict[str, Any]:
    """
    Нормализует строку данных VK Ads для вставки в ClickHouse.
    
    Args:
        row: сырые данные
        account_id: ID аккаунта
        
    Returns:
        Нормализованные данные
    """
    try:
        # Извлечение UTM-меток
        utm_params = extract_utm_params({
            'utm_source': row.get('utm_source', ''),
            'utm_medium': row.get('utm_medium', ''),
            'utm_campaign': row.get('utm_campaign', ''),
            'utm_content': row.get('utm_content', ''),
            'utm_term': row.get('utm_term', '')
        })
        
        # Дополнительный парсинг utm_content
        utm_content = row.get('utm_content', '')
        parsed_utm = parse_utm_content(utm_content)
        
        return {
            'stat_date': to_date(row.get('date')),
            'account_id': account_id,
            'campaign_id': int(row.get('campaign_id', 0)),
            'ad_group_id': int(row.get('adgroup_id', 0)),
            'ad_id': int(row.get('adgroup_id', 0)),  # В VK Ads adgroup_id это ad_id
            'impressions': int(row.get('impressions', 0)),
            'clicks': int(row.get('clicks', 0)),
            'spent': float(row.get('cost', 0)),
            'utm_source': utm_params.get('utm_source', ''),
            'utm_medium': utm_params.get('utm_medium', ''),
            'utm_campaign': utm_params.get('utm_campaign', ''),
            'utm_content': utm_content,
            'utm_city': parsed_utm.get('utm_city', '') if parsed_utm else '',
            'utm_day': parsed_utm.get('utm_day', 0) if parsed_utm else 0,
            'utm_month': parsed_utm.get('utm_month', 0) if parsed_utm else 0,
            '_ver': now_msk()
        }
    except Exception as e:
        logger.warning(f"Ошибка при нормализации строки: {e}")
        return None

class VkAdsLoader:
    """Загрузчик данных VK Ads в ClickHouse."""
    
    def __init__(self, ch_client: ClickHouseClient, api_client: VkAdsClient, account_ids: List[int]):
        """
        Инициализация загрузчика.
        
        Args:
            ch_client: клиент ClickHouse
            api_client: клиент VK Ads API
            account_ids: список ID аккаунтов
        """
        self.ch_client = ch_client
        self.api_client = api_client
        self.account_ids = account_ids
    
    def _load_campaigns(self, account_id: int, client_id: int = None) -> Dict[int, Dict]:
        """
        Загружает метаданные кампаний.
        
        Args:
            account_id: ID аккаунта
            client_id: ID клиента
            
        Returns:
            Словарь с метаданными кампаний
        """
        try:
            campaigns = self.api_client.get_campaigns(
                account_id=account_id,
                client_id=client_id
            )
            return {int(item["id"]): item for item in campaigns if "id" in item}
        except Exception as e:
            logger.error(f"Ошибка при загрузке кампаний: {e}")
            return {}
    
    def _load_ads(self, account_id: int, campaign_ids: List[int], client_id: int = None) -> Dict[int, Dict]:
        """
        Загружает метаданные объявлений.
        
        Args:
            account_id: ID аккаунта
            campaign_ids: список ID кампаний
            client_id: ID клиента
            
        Returns:
            Словарь с метаданными объявлений
        """
        try:
            ads = self.api_client.get_ads(
                account_id=account_id,
                campaign_ids=campaign_ids,
                client_id=client_id
            )
            return {int(item["id"]): item for item in ads if "id" in item}
        except Exception as e:
            logger.error(f"Ошибка при загрузке объявлений: {e}")
            return {}
    
    def _normalize_statistics(
        self,
        stats: List[Dict],
        ads_meta: Dict[int, Dict],
        campaigns_meta: Dict[int, Dict]
    ) -> List[Dict[str, Any]]:
        """
        Нормализует статистику.
        
        Args:
            stats: сырая статистика
            ads_meta: метаданные объявлений
            campaigns_meta: метаданные кампаний
            
        Returns:
            Нормализованные данные
        """
        rows = []
        
        # Создаем словарь с названиями кампаний
        campaign_names = {}
        for cid, info in campaigns_meta.items():
            name = info.get("name") or info.get("title")
            if name:
                campaign_names[int(cid)] = str(name)
        
        for item in stats:
            ident = item.get("id")
            if ident is None:
                continue
            
            entries = item.get("stats") or []
            meta = ads_meta.get(int(ident), {})
            campaign_id = meta.get("campaign_id") or item.get("campaign_id") or ident
            campaign_id = int(campaign_id)
            adgroup_id = int(meta.get("id") or ident)
            
            # Парсим UTM из URL объявления
            utm = parse_utm_from_url(
                meta.get("link_url") or meta.get("link_href") or meta.get("domain")
            )
            
            for entry in entries:
                # Нормализация даты
                day = entry.get("day")
                if day:
                    try:
                        dt = datetime.fromisoformat(day.replace("Z", "+00:00"))
                        day = dt.date().isoformat()
                    except ValueError:
                        day = day[:10]
                else:
                    day = entry.get("month", "")[:10]
                
                row = {
                    'date': day,
                    'campaign_id': str(campaign_id),
                    'campaign_name': campaign_names.get(int(campaign_id), ""),
                    'adgroup_id': str(adgroup_id),
                    'adgroup_name': meta.get("name", ""),
                    'cost': str(float(entry.get("spent", 0))),
                    'clicks': str(int(entry.get("clicks", 0))),
                    'impressions': str(int(entry.get("impressions", 0))),
                    'city': meta.get("cities", ""),
                    'utm_source': utm.get("utm_source", ""),
                    'utm_medium': utm.get("utm_medium", ""),
                    'utm_campaign': utm.get("utm_campaign", ""),
                    'utm_content': utm.get("utm_content", ""),
                    'utm_term': utm.get("utm_term", ""),
                }
                rows.append(row)
            
            # Если нет статистики, добавляем пустую строку
            if not entries:
                row = {
                    'date': '',
                    'campaign_id': str(campaign_id),
                    'campaign_name': campaign_names.get(int(campaign_id), ""),
                    'adgroup_id': str(adgroup_id),
                    'adgroup_name': meta.get("name", ""),
                    'cost': '0',
                    'clicks': '0',
                    'impressions': '0',
                    'city': meta.get("cities", ""),
                    'utm_source': utm.get("utm_source", ""),
                    'utm_medium': utm.get("utm_medium", ""),
                    'utm_campaign': utm.get("utm_campaign", ""),
                    'utm_content': utm.get("utm_content", ""),
                    'utm_term': utm.get("utm_term", ""),
                }
                rows.append(row)
        
        return rows
    
    @log_data_operation(logger, 'load', 'vk_ads_api', 'clickhouse')
    def load_statistics(
        self, 
        date_from: date = None, 
        date_to: date = None,
        client_id: int = None
    ) -> int:
        """
        Загружает статистику в ClickHouse.
        
        Args:
            date_from: начальная дата
            date_to: конечная дата
            client_id: ID клиента
            
        Returns:
            Количество загруженных строк
        """
        if not date_from:
            date_from = days_ago(int(os.getenv('VK_DAYS_BACK', 30)))
        if not date_to:
            date_to = today_msk()
        
        logger.info(f"Загрузка статистики VK Ads за период {date_from} - {date_to}")
        
        total_rows = 0
        
        for account_id in self.account_ids:
            logger.info(f"Загрузка данных для аккаунта {account_id}")
            
            try:
                # Загрузка метаданных
                campaigns_meta = self._load_campaigns(account_id, client_id)
                ads_meta = self._load_ads(account_id, list(campaigns_meta.keys()), client_id)
                
                if not campaigns_meta:
                    logger.warning(f"Нет кампаний для аккаунта {account_id}")
                    continue
                
                # Определяем источник IDs (кампании или объявления)
                ids_source = list(ads_meta.keys()) if ads_meta else list(campaigns_meta.keys())
                ids_type = "ad" if ads_meta else "campaign"
                
                # Загрузка статистики по чанкам
                all_stats = []
                for chunk in _chunked(ids_source, size=200):
                    logger.debug(f"Загрузка чанка статистики размером {len(chunk)}")
                    
                    try:
                        batch = self.api_client.get_statistics(
                            account_id=account_id,
                            client_id=client_id,
                            ids_type=ids_type,
                            ids=chunk,
                            period="day",
                            date_from=date_from.isoformat(),
                            date_to=date_to.isoformat(),
                            metrics=["impressions", "clicks", "spent"]
                        )
                        all_stats.extend(batch)
                    except VkAdsError as e:
                        logger.error(f"Ошибка загрузки чанка {chunk}: {e}")
                        continue
                
                # Нормализация данных
                normalized_rows = self._normalize_statistics(
                    all_stats, ads_meta, campaigns_meta
                )
                
                # Дополнительная нормализация для ClickHouse
                ch_rows = []
                for row in normalized_rows:
                    ch_row = normalize_vk_ads_row(row, account_id)
                    if ch_row:
                        ch_rows.append(ch_row)
                
                if ch_rows:
                    # Загрузка в ClickHouse
                    self.ch_client.insert('zakaz.fact_vk_ads_daily', ch_rows)
                    total_rows += len(ch_rows)
                    logger.info(f"Загружено {len(ch_rows)} строк для аккаунта {account_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных для аккаунта {account_id}: {e}")
                continue
        
        logger.info(f"Всего загружено {total_rows} строк")
        return total_rows

def record_job_run(ch_client: ClickHouseClient, job: str, status: str, 
                  rows_processed: int = 0, message: str = "", 
                  metrics: Dict[str, Any] = None) -> None:
    """
    Запись информации о запуске задачи в ClickHouse.
    
    Args:
        ch_client: клиент ClickHouse
        job: название задачи
        status: статус (success, error, running)
        rows_processed: количество обработанных строк
        message: сообщение
        metrics: метрики
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
    parser = argparse.ArgumentParser(description='VK Ads загрузчик')
    parser.add_argument('--days', type=int, help='Количество дней для загрузки')
    parser.add_argument('--since', type=str, help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--to', type=str, help='Конечная дата в формате YYYY-MM-DD')
    parser.add_argument('--accounts', type=str, help='ID аккаунтов через запятую')
    parser.add_argument('--env', type=str, default='secrets/.env.vk', 
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
        date_from = days_ago(int(os.getenv('VK_DAYS_BACK', 30)))
    
    if args.to:
        date_to = to_date(args.to)
    
    # Определение аккаунтов
    if args.accounts:
        account_ids = [int(acc.strip()) for acc in args.accounts.split(',')]
    else:
        account_ids_str = os.getenv('VK_ACCOUNT_IDS', '')
        account_ids = [int(acc.strip()) for acc in account_ids_str.split(',') if acc.strip()]
    
    if not account_ids:
        logger.error("Не указаны ID аккаунтов")
        sys.exit(1)
    
    try:
        # Инициализация клиентов
        ch_client = get_client(args.env)
        
        with VkAdsClient(
            access_token=os.getenv('VK_TOKEN'),
            api_version=os.getenv('VK_API_VERSION', '5.131'),
            timeout=int(os.getenv('VK_TIMEOUT', 30))
        ) as api_client:
            
            loader = VkAdsLoader(ch_client, api_client, account_ids)
            
            # Запись о начале работы
            record_job_run(ch_client, 'vk_ads_loader', 'running')
            
            # Загрузка данных
            rows_count = loader.load_statistics(date_from, date_to)
            
            # Запись об успешном завершении
            record_job_run(
                ch_client, 'vk_ads_loader', 'success', 
                rows_count, f"Загружено строк: {rows_count}"
            )
            
            logger.info(f"Загрузка успешно завершена, загружено строк: {rows_count}")
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении загрузчика: {e}")
        
        # Попытка записи об ошибке
        try:
            ch_client = get_client(args.env)
            record_job_run(ch_client, 'vk_ads_loader', 'error', 0, str(e))
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main()