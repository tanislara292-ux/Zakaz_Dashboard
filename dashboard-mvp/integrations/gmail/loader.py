"""
Gmail инжестор (резервный канал).
Загружает данные о продажах из писем Gmail в ClickHouse.
"""

import os
import sys
import base64
import hashlib
import argparse
import json
import datetime as dt
import email
from email.utils import parsedate_to_datetime
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, today_msk, to_date, days_ago,
    setup_integrations_logger, log_data_operation
)

# Настройка логгера
logger = setup_integrations_logger('gmail')

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailClient:
    """Клиент для работы с Gmail API."""
    
    def __init__(self, credentials_path: str, token_path: str):
        """
        Инициализация клиента Gmail API.
        
        Args:
            credentials_path: путь к файлу credentials.json
            token_path: путь к файлу token.json
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
    
    def authenticate(self):
        """Аутентификация в Gmail API."""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'w') as f:
                f.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        return self.service
    
    def get_messages(self, query: str, max_results: int = 1000) -> List[str]:
        """
        Получение списка ID сообщений.
        
        Args:
            query: поисковый запрос
            max_results: максимальное количество результатов
            
        Returns:
            Список ID сообщений
        """
        if not self.service:
            self.authenticate()
        
        try:
            result = self.service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()
            
            message_ids = [m['id'] for m in result.get('messages', [])]
            logger.info(f"Найдено сообщений: {len(message_ids)}")
            return message_ids
        except Exception as e:
            logger.error(f"Ошибка при получении списка сообщений: {e}")
            raise
    
    def get_message(self, message_id: str) -> Dict[str, Any]:
        """
        Получение сообщения по ID.
        
        Args:
            message_id: ID сообщения
            
        Returns:
            Данные сообщения
        """
        if not self.service:
            self.authenticate()
        
        try:
            message = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            return message
        except Exception as e:
            logger.error(f"Ошибка при получении сообщения {message_id}: {e}")
            raise
    
    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """
        Получение вложения.
        
        Args:
            message_id: ID сообщения
            attachment_id: ID вложения
            
        Returns:
            Данные вложения
        """
        if not self.service:
            self.authenticate()
        
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me', messageId=message_id, id=attachment_id
            ).execute()
            
            return base64.urlsafe_b64decode(attachment['data'].encode('utf-8'))
        except Exception as e:
            logger.error(f"Ошибка при получении вложения: {e}")
            raise

class GmailLoader:
    """Загрузчик данных Gmail в ClickHouse."""
    
    def __init__(self, ch_client: ClickHouseClient, gmail_client: GmailClient, decimal_comma: bool = True):
        """
        Инициализация загрузчика.
        
        Args:
            ch_client: клиент ClickHouse
            gmail_client: клиент Gmail API
            decimal_comma: использовать запятую как десятичный разделитель
        """
        self.ch_client = ch_client
        self.gmail_client = gmail_client
        self.decimal_comma = decimal_comma
    
    def _decode_data(self, data_b64: str) -> bytes:
        """Декодирование base64 данных."""
        return base64.urlsafe_b64decode(data_b64.encode('utf-8'))
    
    def _parse_number(self, s: str) -> float:
        """Парсинг числа с учетом разделителей."""
        if s is None:
            return 0.0
        
        s = str(s).strip().replace(' ', '')
        if s == '' or s == '-':
            return 0.0
        
        if self.decimal_comma:
            s = s.replace('\u00a0', '').replace(',', '.')
        
        try:
            return float(s)
        except ValueError:
            # Может быть "12 345,67 RUB"
            s = ''.join(ch for ch in s if ch.isdigit() or ch in '.,-')
            if self.decimal_comma:
                s = s.replace(',', '.')
            return float(s) if s else 0.0
    
    def _norm_text(self, s: str) -> str:
        """Нормализация текста."""
        return (s or '').strip()
    
    def _extract_msg_meta(self, msg: Dict[str, Any]) -> Tuple[str, dt.datetime]:
        """Извлечение метаданных сообщения."""
        headers = msg.get('payload', {}).get('headers', [])
        hdr = {h['name'].lower(): h['value'] for h in headers}
        msg_id = hdr.get('message-id') or msg.get('id')
        internal_ms = int(msg.get('internalDate', '0'))
        recv_at = dt.datetime.utcfromtimestamp(internal_ms/1000.0)
        return msg_id, recv_at
    
    def _iter_parts(self, payload: Dict[str, Any]):
        """Итератор по частям сообщения."""
        if 'parts' in payload:
            for p in payload['parts']:
                if 'parts' in p:
                    for sp in self._iter_parts(p):
                        yield sp
                else:
                    yield p
        else:
            yield payload
    
    def _tables_from_html(self, html_bytes: bytes) -> List[pd.DataFrame]:
        """Извлечение таблиц из HTML."""
        try:
            dfs = pd.read_html(html_bytes, flavor='lxml')
            return dfs
        except ValueError:
            # Нет таблиц - попробуем вытащить <table> вручную
            soup = BeautifulSoup(html_bytes, 'lxml')
            tables = soup.find_all('table')
            dfs = []
            for t in tables:
                try:
                    dfs.append(pd.read_html(str(t))[0])
                except Exception:
                    pass
            return dfs
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Нормализация колонок DataFrame."""
        # Возможные рус/англ заголовки
        col_map = {
            'date': ['date','дата','event_date','дата события'],
            'event_id': ['event_id','ид события','идентификатор'],
            'event_name': ['event','событие','название события'],
            'city': ['city','город'],
            'tickets_sold': ['tickets_sold','продано билетов','билетов'],
            'revenue': ['revenue','выручка','сумма','сумма продажи'],
            'refunds': ['refunds','возвраты','refund'],
            'currency': ['currency','валюта'],
        }
        
        # Нижний регистр без пробелов/символов
        def key(s): return ''.join(ch.lower() for ch in str(s) if ch.isalnum() or ch in ' _').strip()
        rename = {}
        cols_norm = {key(c): c for c in df.columns}
        
        for target, alts in col_map.items():
            for alt in alts:
                k = key(alt)
                for c_key, c_name in cols_norm.items():
                    if c_key == k:
                        rename[c_name] = target
                        break
                if target in rename.values():
                    break
        
        df = df.rename(columns=rename)
        return df
    
    def _normalize_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Нормализация строк DataFrame."""
        # Обязательные поля
        for col in ['date','event_name','city']:
            if col not in df.columns:
                df[col] = None
        if 'event_id' not in df.columns:
            df['event_id'] = None
        if 'tickets_sold' not in df.columns:
            df['tickets_sold'] = 0
        if 'revenue' not in df.columns:
            df['revenue'] = 0.0
        if 'refunds' not in df.columns:
            df['refunds'] = 0.0
        if 'currency' not in df.columns:
            df['currency'] = 'RUB'
        
        # Приведение типов
        def to_date(x):
            if pd.isna(x):
                return None
            s = str(x).strip()
            for fmt in ('%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
                try:
                    return pd.to_datetime(s, format=fmt).date()
                except Exception:
                    pass
            # Последняя попытка: pandas parse
            try:
                return pd.to_datetime(s, dayfirst=True).date()
            except Exception:
                return None
        
        df_out = pd.DataFrame({
            'event_date': df['date'].map(to_date),
            'event_id': df['event_id'].map(self._norm_text),
            'event_name': df['event_name'].map(self._norm_text),
            'city': df['city'].map(self._norm_text),
            'tickets_sold': df['tickets_sold'].map(lambda v: int(float(str(v).replace(',', '.')) if str(v).strip() else 0)),
            'revenue': df['revenue'].map(lambda s: self._parse_number(s)),
            'refunds': df['refunds'].map(lambda s: self._parse_number(s)),
            'currency': df['currency'].map(lambda s: (s or 'RUB').strip()[:8]),
        })
        
        # Фильтр пустых
        df_out = df_out[df_out['event_date'].notna() & df_out['city'].astype(str).str.len().gt(0)]
        return df_out
    
    def _hash_row(self, r: pd.Series) -> str:
        """Вычисление хеша строки для дедупликации."""
        payload = f"{r['event_date']}|{(r['event_name'] or '').lower()}|{(r['city'] or '').lower()}|{r['tickets_sold']}|{r['revenue']}|{r['refunds']}|{r['currency']}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def _extract_rows_from_message(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлечение строк данных из сообщения."""
        msg_id, recv_at = self._extract_msg_meta(msg)
        payload = msg.get('payload', {})
        rows = []
        
        # 1) Вложения (csv/xls/xlsx)
        got_any = False
        for part in self._iter_parts(payload):
            mime = part.get('mimeType', '')
            filename = part.get('filename', '')
            body = part.get('body', {})
            attach_id = body.get('attachmentId')
            
            if not filename and mime == 'text/html' and 'data' in body:
                # Inline HTML body
                html_bytes = self._decode_data(body['data'])
                for df in self._tables_from_html(html_bytes):
                    df = self._normalize_columns(df)
                    df = self._normalize_rows(df)
                    if len(df):
                        got_any = True
                        for _, r in df.iterrows():
                            rows.append((msg_id, recv_at, r))
            elif attach_id and (filename.endswith('.csv') or filename.endswith('.CSV')):
                try:
                    content = self.gmail_client.get_attachment(msg['id'], attach_id)
                    # Autodetect sep ; or , and encoding
                    try_list = [
                        dict(sep=';', encoding='utf-8'),
                        dict(sep=',', encoding='utf-8'),
                        dict(sep=';', encoding='cp1251'),
                        dict(sep=',', encoding='cp1251'),
                    ]
                    parsed = False
                    for opt in try_list:
                        try:
                            df = pd.read_csv(pd.io.common.BytesIO(content), **opt)
                            df = self._normalize_columns(df)
                            df = self._normalize_rows(df)
                            if len(df):
                                parsed = True
                                got_any = True
                                for _, r in df.iterrows():
                                    rows.append((msg_id, recv_at, r))
                                break
                        except Exception:
                            continue
                    if not parsed:
                        logger.warning(f"Не удалось распарсить CSV: {filename}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке вложения {filename}: {e}")
        
        # 2) Если ничего не нашли - пробуем основной body как HTML
        if not got_any:
            data = payload.get('body', {}).get('data')
            if data:
                html_bytes = self._decode_data(data)
                for df in self._tables_from_html(html_bytes):
                    df = self._normalize_columns(df)
                    df = self._normalize_rows(df)
                    for _, r in df.iterrows():
                        rows.append((msg_id, recv_at, r))
        
        # Финальная нормализация и хэши
        out = []
        for mid, rcv, r in rows:
            row_hash = self._hash_row(r)
            out.append({
                'src_msg_id': mid,
                'ingested_at': now_msk(),
                'event_date': r['event_date'],
                'event_id': r['event_id'] or '',
                'event_name': r['event_name'] or '',
                'city': r['city'] or '',
                'tickets_sold': int(r['tickets_sold'] or 0),
                'revenue': float(r['revenue'] or 0.0),
                'refunds': float(r['refunds'] or 0.0),
                'currency': r['currency'] or 'RUB',
                '_ver': now_msk()
            })
        return out
    
    @log_data_operation(logger, 'load', 'gmail_api', 'clickhouse')
    def load_messages(self, query: str, limit: int = None) -> int:
        """
        Загружает сообщения в ClickHouse.
        
        Args:
            query: поисковый запрос
            limit: ограничение количества сообщений
            
        Returns:
            Количество загруженных строк
        """
        logger.info(f"Загрузка сообщений по запросу: {query}")
        
        try:
            # Получение списка сообщений
            message_ids = self.gmail_client.get_messages(query)
            
            if limit:
                message_ids = message_ids[:limit]
            
            if not message_ids:
                logger.warning("Сообщения не найдены")
                return 0
            
            # Обработка сообщений
            all_rows = []
            for i, message_id in enumerate(message_ids, 1):
                try:
                    message = self.gmail_client.get_message(message_id)
                    rows = self._extract_rows_from_message(message)
                    all_rows.extend(rows)
                    logger.info(f"Обработано {i}/{len(message_ids)} сообщений, строк: {len(rows)}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке сообщения {message_id}: {e}")
                    continue
            
            if not all_rows:
                logger.warning("Нет данных для загрузки")
                return 0
            
            # Загрузка в ClickHouse
            self.ch_client.insert('zakaz.stg_qtickets_sales_raw', all_rows)
            
            logger.info(f"Загружено {len(all_rows)} строк")
            return len(all_rows)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке сообщений: {e}")
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
    parser = argparse.ArgumentParser(description='Gmail инжестор')
    parser.add_argument('--days', type=int, help='Количество дней для поиска')
    parser.add_argument('--query', type=str, help='Поисковый запрос')
    parser.add_argument('--limit', type=int, help='Ограничение количества сообщений')
    parser.add_argument('--dry-run', action='store_true', help='Тестовый запуск без загрузки')
    parser.add_argument('--env', type=str, default='secrets/.env.gmail', 
                       help='Путь к файлу с переменными окружения')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    # Определение поискового запроса
    if args.query:
        query = args.query
    else:
        days = args.days or int(os.getenv('GMAIL_DAYS_BACK', 7))
        query = os.getenv('GMAIL_QUERY', f'subject:QTickets OR subject:qTickets OR from:qtickets.ru newer_than:{days}d')
    
    # Проверка обязательных параметров
    creds_path = os.getenv('GMAIL_CREDENTIALS_PATH')
    token_path = os.getenv('GMAIL_TOKEN_PATH')
    
    if not creds_path or not token_path:
        logger.error("Не указаны обязательные параметры GMAIL_CREDENTIALS_PATH или GMAIL_TOKEN_PATH")
        sys.exit(1)
    
    try:
        # Инициализация клиентов
        ch_client = get_client(args.env)
        gmail_client = GmailClient(creds_path, token_path)
        gmail_client.authenticate()
        
        loader = GmailLoader(
            ch_client, gmail_client, 
            decimal_comma=os.getenv('DECIMAL_COMMA', 'true').lower() == 'true'
        )
        
        # Запись о начале работы
        record_job_run(ch_client, 'gmail_loader', 'running')
        
        if args.dry_run:
            # Тестовый запуск
            message_ids = gmail_client.get_messages(query, limit=args.limit or 10)
            logger.info(f"Найдено сообщений: {len(message_ids)}")
            
            if message_ids:
                message = gmail_client.get_message(message_ids[0])
                rows = loader._extract_rows_from_message(message)
                logger.info(f"Пример данных из сообщения: {json.dumps(rows[:2], indent=2, default=str)}")
        else:
            # Загрузка данных
            rows_count = loader.load_messages(query, args.limit)
            
            # Запись об успешном завершении
            record_job_run(
                ch_client, 'gmail_loader', 'success', 
                rows_count, f"Загружено строк: {rows_count}"
            )
            
            logger.info(f"Загрузка успешно завершена, загружено строк: {rows_count}")
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении инжестора: {e}")
        
        # Попытка записи об ошибке
        try:
            ch_client = get_client(args.env)
            record_job_run(ch_client, 'gmail_loader', 'error', 0, str(e))
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main()