"""
Яндекс.Директ API загрузчик.
Загружает статистику по рекламным кампаниям Яндекс.Директ в ClickHouse.
"""

import os
import sys
import argparse
import json
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, today_msk, to_date, days_ago,
    setup_integrations_logger, log_data_operation,
    parse_utm_content, extract_utm_params
)

# Настройка логгера
logger = setup_integrations_logger('direct')

class DirectAPIClient:
    """Клиент для работы с Яндекс.Директ API."""
    
    def __init__(
        self,
        login: str,
        token: str,
        client_id: str = None,
        api_url: str = None,
        timeout: int = 30
    ):
        """
        Инициализация клиента Яндекс.Директ API.
        
        Args:
            login: логин аккаунта Яндекс.Директ
            token: токен доступа
            client_id: ID клиента (для агентских аккаунтов)
            api_url: URL API
            timeout: таймаут запросов
        """
        self.login = login
        self.token = token
        self.client_id = client_id
        self.api_url = api_url or os.getenv('DIRECT_API_URL', 'https://api.direct.yandex.ru/json/v5')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Client-Login': self.login,
            'Accept-Language': 'ru',
            'Content-Type': 'application/json; charset=utf-8'
        })
        
        if self.client_id:
            self.session.headers.update({
                'Client-Id': self.client_id
            })
    
    def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполнение запроса к API.
        
        Args:
            method: метод API
            params: параметры запроса
            
        Returns:
            Ответ API в виде словаря
        """
        url = f"{self.api_url}/{method}"
        
        try:
            response = self.session.post(url, json=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                error = data['error']
                error_msg = f"Яндекс.Директ API error {error.get('error_code')}: {error.get('error_string')}"
                if 'error_detail' in error:
                    error_msg += f" - {error['error_detail']}"
                raise Exception(error_msg)
            
            return data.get('result', {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к Яндекс.Директ API: {e}")
            raise
    
    def get_campaigns(self, field_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка кампаний.
        
        Args:
            field_names: список полей для получения
            
        Returns:
            Список кампаний
        """
        if not field_names:
            field_names = [
                'Id', 'Name', 'Status', 'State', 'StartDate', 'EndDate',
                'DailyBudget', 'Currency', 'Type'
            ]
        
        params = {
            'method': 'get',
            'params': {
                'SelectionCriteria': {},
                'FieldNames': field_names
            }
        }
        
        logger.info("Загрузка списка кампаний из Яндекс.Директ API")
        
        try:
            data = self._make_request('campaigns', params)
            campaigns = data.get('Campaigns', [])
            
            logger.info(f"Загружено {len(campaigns)} кампаний")
            return campaigns
        except Exception as e:
            logger.error(f"Ошибка при загрузке кампаний: {e}")
            raise
    
    def get_ad_groups(self, campaign_ids: List[int], field_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка групп объявлений.
        
        Args:
            campaign_ids: список ID кампаний
            field_names: список полей для получения
            
        Returns:
            Список групп объявлений
        """
        if not field_names:
            field_names = [
                'Id', 'CampaignId', 'Name', 'Status', 'Type', 'RegionIds'
            ]
        
        params = {
            'method': 'get',
            'params': {
                'SelectionCriteria': {
                    'CampaignIds': campaign_ids
                },
                'FieldNames': field_names
            }
        }
        
        logger.debug(f"Загрузка групп объявлений для {len(campaign_ids)} кампаний")
        
        try:
            data = self._make_request('adgroups', params)
            ad_groups = data.get('AdGroups', [])
            
            logger.debug(f"Загружено {len(ad_groups)} групп объявлений")
            return ad_groups
        except Exception as e:
            logger.error(f"Ошибка при загрузке групп объявлений: {e}")
            raise
    
    def get_ads(self, campaign_ids: List[int], field_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка объявлений.
        
        Args:
            campaign_ids: список ID кампаний
            field_names: список полей для получения
            
        Returns:
            Список объявлений
        """
        if not field_names:
            field_names = [
                'Id', 'CampaignId', 'AdGroupId', 'Title', 'Text', 'Href',
                'Status', 'State', 'Type', 'Mobile', 'VCardId'
            ]
        
        params = {
            'method': 'get',
            'params': {
                'SelectionCriteria': {
                    'CampaignIds': campaign_ids
                },
                'FieldNames': field_names
            }
        }
        
        logger.debug(f"Загрузка объявлений для {len(campaign_ids)} кампаний")
        
        try:
            data = self._make_request('ads', params)
            ads = data.get('Ads', [])
            
            logger.debug(f"Загружено {len(ads)} объявлений")
            return ads
        except Exception as e:
            logger.error(f"Ошибка при загрузке объявлений: {e}")
            raise
    
    def get_report(
        self,
        report_type: str,
        date_from: date,
        date_to: date,
        field_names: List[str],
        filter_criteria: Dict[str, Any] = None,
        include_vat: str = 'YES',
        include_discount: str = 'NO'
    ) -> List[Dict[str, Any]]:
        """
        Получение отчета.
        
        Args:
            report_type: тип отчета
            date_from: начальная дата
            date_to: конечная дата
            field_names: список полей
            filter_criteria: критерии фильтрации
            include_vat: включать НДС
            include_discount: включать скидки
            
        Returns:
            Данные отчета
        """
        params = {
            'method': 'get',
            'params': {
                'SelectionCriteria': filter_criteria or {},
                'DateFrom': date_from.strftime('%Y-%m-%d'),
                'DateTo': date_to.strftime('%Y-%m-%d'),
                'FieldNames': field_names,
                'ReportType': report_type,
                'ReportName': f'report_{report_type}_{date_from}_{date_to}',
                'DateRangeType': 'CUSTOM_DATE',
                'Format': 'TSV',
                'IncludeVAT': include_vat,
                'IncludeDiscount': include_discount
            }
        }
        
        logger.info(f"Запрос отчета {report_type} за период {date_from} - {date_to}")
        
        try:
            # Отправляем запрос на создание отчета
            response = self.session.post(
                f"{self.api_url}/reports",
                json=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Проверяем ответ
            if response.status_code == 200:
                # Парсим TSV ответ
                lines = response.text.strip().split('\n')
                if len(lines) < 2:
                    return []
                
                headers = lines[0].split('\t')
                data = []
                
                for line in lines[1:]:
                    values = line.split('\t')
                    if len(values) == len(headers):
                        row = dict(zip(headers, values))
                        data.append(row)
                
                logger.info(f"Получено {len(data)} строк в отчете {report_type}")
                return data
            else:
                logger.error(f"Ошибка получения отчета: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при получении отчета {report_type}: {e}")
            raise

class DirectLoader:
    """Загрузчик данных Яндекс.Директ в ClickHouse."""
    
    def __init__(self, ch_client: ClickHouseClient, api_client: DirectAPIClient):
        """
        Инициализация загрузчика.
        
        Args:
            ch_client: клиент ClickHouse
            api_client: клиент Яндекс.Директ API
        """
        self.ch_client = ch_client
        self.api_client = api_client
    
    def normalize_direct_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует строку данных Яндекс.Директ для вставки в ClickHouse.
        
        Args:
            row: сырые данные
            
        Returns:
            Нормализованные данные
        """
        try:
            # Извлечение UTM-меток
            utm_params = extract_utm_params({
                'utm_source': row.get('UtmSource', ''),
                'utm_medium': row.get('UtmMedium', ''),
                'utm_campaign': row.get('UtmCampaign', ''),
                'utm_content': row.get('UtmContent', ''),
                'utm_term': row.get('UtmTerm', '')
            })
            
            # Дополнительный парсинг utm_content
            utm_content = row.get('UtmContent', '')
            parsed_utm = parse_utm_content(utm_content)
            
            # Конвертация даты
            stat_date = row.get('Date')
            if stat_date:
                try:
                    # Формат YYYY-MM-DD
                    stat_date = datetime.strptime(stat_date, '%Y-%m-%d').date()
                except ValueError:
                    # Пробуем другие форматы
                    try:
                        stat_date = datetime.strptime(stat_date, '%d.%m.%Y').date()
                    except ValueError:
                        logger.warning(f"Не удалось распарсить дату: {stat_date}")
                        return None
            
            return {
                'stat_date': stat_date,
                'account_login': self.api_client.login,
                'campaign_id': int(row.get('CampaignId', 0)),
                'ad_group_id': int(row.get('AdGroupId', 0)),
                'ad_id': int(row.get('AdId', 0)),
                'impressions': int(row.get('Impressions', 0)),
                'clicks': int(row.get('Clicks', 0)),
                'cost': float(Decimal(str(row.get('Cost', 0)))),
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
    
    @log_data_operation(logger, 'load', 'direct_api', 'clickhouse')
    def load_statistics(
        self, 
        date_from: date = None, 
        date_to: date = None
    ) -> int:
        """
        Загружает статистику в ClickHouse.
        
        Args:
            date_from: начальная дата
            date_to: конечная дата
            
        Returns:
            Количество загруженных строк
        """
        if not date_from:
            date_from = days_ago(int(os.getenv('DIRECT_DAYS_BACK', 30)))
        if not date_to:
            date_to = today_msk()
        
        logger.info(f"Загрузка статистики Яндекс.Директ за период {date_from} - {date_to}")
        
        try:
            # Запрос отчета с детализацией по объявлениям
            field_names = [
                'Date',
                'CampaignId',
                'AdGroupId',
                'AdId',
                'Impressions',
                'Clicks',
                'Cost',
                'UtmSource',
                'UtmMedium',
                'UtmCampaign',
                'UtmContent',
                'UtmTerm'
            ]
            
            report_data = self.api_client.get_report(
                report_type='CUSTOM_REPORT',
                date_from=date_from,
                date_to=date_to,
                field_names=field_names,
                filter_criteria={
                    'Status': ['ACCEPTED', 'ACCEPTED_WITH_COMMENT']
                }
            )
            
            if not report_data:
                logger.warning("Нет данных для загрузки")
                return 0
            
            # Нормализация данных
            normalized_rows = []
            for row in report_data:
                normalized_row = self.normalize_direct_row(row)
                if normalized_row:
                    normalized_rows.append(normalized_row)
            
            if not normalized_rows:
                logger.warning("Нет нормализованных данных для загрузки")
                return 0
            
            # Загрузка в ClickHouse
            self.ch_client.insert('zakaz.fact_direct_daily', normalized_rows)
            
            logger.info(f"Загружено {len(normalized_rows)} строк")
            return len(normalized_rows)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке статистики: {e}")
            raise

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
    parser = argparse.ArgumentParser(description='Яндекс.Директ загрузчик')
    parser.add_argument('--days', type=int, help='Количество дней для загрузки')
    parser.add_argument('--since', type=str, help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--to', type=str, help='Конечная дата в формате YYYY-MM-DD')
    parser.add_argument('--env', type=str, default='secrets/.env.direct', 
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
        date_from = days_ago(int(os.getenv('DIRECT_DAYS_BACK', 30)))
    
    if args.to:
        date_to = to_date(args.to)
    
    # Проверка обязательных параметров
    login = os.getenv('DIRECT_LOGIN')
    token = os.getenv('DIRECT_TOKEN')
    
    if not login or not token:
        logger.error("Не указаны обязательные параметры DIRECT_LOGIN или DIRECT_TOKEN")
        sys.exit(1)
    
    try:
        # Инициализация клиентов
        ch_client = get_client(args.env)
        
        api_client = DirectAPIClient(
            login=login,
            token=token,
            client_id=os.getenv('DIRECT_CLIENT_ID'),
            api_url=os.getenv('DIRECT_API_URL'),
            timeout=int(os.getenv('DIRECT_TIMEOUT', 30))
        )
        
        loader = DirectLoader(ch_client, api_client)
        
        # Запись о начале работы
        record_job_run(ch_client, 'direct_loader', 'running')
        
        # Загрузка данных
        rows_count = loader.load_statistics(date_from, date_to)
        
        # Запись об успешном завершении
        record_job_run(
            ch_client, 'direct_loader', 'success', 
            rows_count, f"Загружено строк: {rows_count}"
        )
        
        logger.info(f"Загрузка успешно завершена, загружено строк: {rows_count}")
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении загрузчика: {e}")
        
        # Попытка записи об ошибке
        try:
            ch_client = get_client(args.env)
            record_job_run(ch_client, 'direct_loader', 'error', 0, str(e))
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main()