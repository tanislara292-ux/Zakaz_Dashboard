import os
import sys
import base64
import hashlib
import argparse
import datetime as dt
import email
from email.utils import parsedate_to_datetime

import pandas as pd
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from clickhouse_connect import get_client
from dotenv import load_dotenv

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def load_env():
    load_dotenv()
    cfg = {
        'gmail_query': os.getenv('GMAIL_QUERY', 'newer_than:14d'),
        'creds_path': os.getenv('GMAIL_CREDS_PATH', 'secrets/gmail/credentials.json'),
        'token_path': os.getenv('GMAIL_TOKEN_PATH', 'secrets/gmail/token.json'),
        'ch_host': os.getenv('CH_HOST', 'localhost'),
        'ch_port': int(os.getenv('CH_PORT', '443')),
        'ch_secure': os.getenv('CH_SECURE', 'true').lower() == 'true',
        'ch_user': os.getenv('CH_USERNAME', 'etl_writer'),
        'ch_pass': os.getenv('CH_PASSWORD', ''),
        'ch_db': os.getenv('CH_DATABASE', 'zakaz'),
        'decimal_comma': os.getenv('DECIMAL_COMMA', 'true').lower() == 'true',
    }
    return cfg

def auth_gmail(creds_path: str, token_path: str):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)

def ch_client(cfg):
    return get_client(
        host=cfg['ch_host'],
        port=cfg['ch_port'],
        username=cfg['ch_user'],
        password=cfg['ch_pass'],
        database=cfg['ch_db'],
        secure=cfg['ch_secure'],
        verify=True,
    )

def _decode_data(data_b64: str) -> bytes:
    return base64.urlsafe_b64decode(data_b64.encode('utf-8'))

def _parse_number(s: str, decimal_comma: bool):
    if s is None:
        return 0.0
    s = str(s).strip().replace(' ', '')
    if s == '' or s == '-':
        return 0.0
    if decimal_comma:
        s = s.replace('\u00a0', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        # может быть "12 345,67 RUB"
        s = ''.join(ch for ch in s if ch.isdigit() or ch in '.,-')
        if decimal_comma:
            s = s.replace(',', '.')
        return float(s) if s else 0.0

def _norm_text(s: str) -> str:
    return (s or '').strip()

def _extract_msg_meta(msg):
    headers = msg.get('payload', {}).get('headers', [])
    hdr = {h['name'].lower(): h['value'] for h in headers}
    msg_id = hdr.get('message-id') or msg.get('id')
    internal_ms = int(msg.get('internalDate', '0'))
    recv_at = dt.datetime.utcfromtimestamp(internal_ms/1000.0)
    return msg_id, recv_at

def _iter_parts(payload):
    if 'parts' in payload:
        for p in payload['parts']:
            if 'parts' in p:
                for sp in _iter_parts(p):
                    yield sp
            else:
                yield p
    else:
        yield payload

def _tables_from_html(html_bytes: bytes) -> list[pd.DataFrame]:
    try:
        dfs = pd.read_html(html_bytes, flavor='lxml')
        return dfs
    except ValueError:
        # нет таблиц — попробуем вытащить <table> вручную
        soup = BeautifulSoup(html_bytes, 'lxml')
        tables = soup.find_all('table')
        dfs = []
        for t in tables:
            try:
                dfs.append(pd.read_html(str(t))[0])
            except Exception:
                pass
        return dfs

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
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
    # нижний регистр без пробелов/символов
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

def _normalize_rows(df: pd.DataFrame, decimal_comma: bool) -> pd.DataFrame:
    # обязательные поля
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

    # приведение типов
    def to_date(x):
        if pd.isna(x):
            return None
        s = str(x).strip()
        for fmt in ('%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
            try:
                return pd.to_datetime(s, format=fmt).date()
            except Exception:
                pass
        # last chance: pandas parse
        try:
            return pd.to_datetime(s, dayfirst=True).date()
        except Exception:
            return None

    df_out = pd.DataFrame({
        'event_date': df['date'].map(to_date),
        'event_id': df['event_id'].map(_norm_text),
        'event_name': df['event_name'].map(_norm_text),
        'city': df['city'].map(_norm_text),
        'tickets_sold': df['tickets_sold'].map(lambda v: int(float(str(v).replace(',', '.')) if str(v).strip() else 0)),
        'revenue': df['revenue'].map(lambda s: _parse_number(s, decimal_comma)),
        'refunds': df['refunds'].map(lambda s: _parse_number(s, decimal_comma)),
        'currency': df['currency'].map(lambda s: (s or 'RUB').strip()[:8]),
    })
    # фильтр пустых
    df_out = df_out[df_out['event_date'].notna() & df_out['city'].astype(str).str.len().gt(0)]
    return df_out

def _hash_row(r: pd.Series) -> str:
    payload = f"{r['event_date']}|{(r['event_name'] or '').lower()}|{(r['city'] or '').lower()}|{r['tickets_sold']}|{r['revenue']}|{r['refunds']}|{r['currency']}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def extract_rows_from_message(service, user_id, msg, decimal_comma: bool):
    msg_id, recv_at = _extract_msg_meta(msg)
    payload = msg.get('payload', {})
    rows = []

    # 1) attachments (csv/xls/xlsx)
    got_any = False
    for part in _iter_parts(payload):
        mime = part.get('mimeType', '')
        filename = part.get('filename', '')
        body = part.get('body', {})
        attach_id = body.get('attachmentId')
        if not filename and mime == 'text/html' and 'data' in body:
            # inline HTML body
            html_bytes = _decode_data(body['data'])
            for df in _tables_from_html(html_bytes):
                df = _normalize_columns(df)
                df = _normalize_rows(df, decimal_comma)
                if len(df):
                    got_any = True
                    for _, r in df.iterrows():
                        rows.append((msg_id, recv_at, r))
        elif attach_id and (filename.endswith('.csv') or filename.endswith('.CSV')):
            att = service.users().messages().attachments().get(userId=user_id, messageId=msg['id'], id=attach_id).execute()
            content = _decode_data(att['data'])
            # autodetect sep ; or , and encoding
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
                    df = _normalize_columns(df)
                    df = _normalize_rows(df, decimal_comma)
                    if len(df):
                        parsed = True
                        got_any = True
                        for _, r in df.iterrows():
                            rows.append((msg_id, recv_at, r))
                        break
                except Exception:
                    continue
            if not parsed:
                print(f"[WARN] CSV parse failed: {filename}", file=sys.stderr)
        # можно добавить xlsx при необходимости

    # 2) если ничего не нашли — пробуем основной body как HTML
    if not got_any:
        data = payload.get('body', {}).get('data')
        if data:
            html_bytes = _decode_data(data)
            for df in _tables_from_html(html_bytes):
                df = _normalize_columns(df)
                df = _normalize_rows(df, decimal_comma)
                for _, r in df.iterrows():
                    rows.append((msg_id, recv_at, r))

    # финальная нормализация и хэши
    out = []
    for mid, rcv, r in rows:
        row_hash = _hash_row(r)
        out.append({
            'msg_id': mid,
            'msg_received_at': rcv,
            'source': 'gmail',
            'event_date': r['event_date'],
            'event_id': r['event_id'] or '',
            'event_name': r['event_name'] or '',
            'city': r['city'] or '',
            'tickets_sold': int(r['tickets_sold'] or 0),
            'revenue': float(r['revenue'] or 0.0),
            'refunds': float(r['refunds'] or 0.0),
            'currency': r['currency'] or 'RUB',
            'row_hash': row_hash,
        })
    return out

def ingest(cfg, limit: int | None = None, dry_run: bool = False):
    service = auth_gmail(cfg['creds_path'], cfg['token_path'])
    user_id = 'me'
    q = cfg['gmail_query']
    print(f"[INFO] Gmail query: {q}")
    res = service.users().messages().list(userId=user_id, q=q, maxResults=1000).execute()
    msg_ids = [m['id'] for m in res.get('messages', [])]
    print(f"[INFO] Messages found: {len(msg_ids)}")
    if limit:
        msg_ids = msg_ids[:limit]

    all_rows = []
    for i, mid in enumerate(msg_ids, 1):
        try:
            msg = service.users().messages().get(userId=user_id, id=mid, format='full').execute()
            rows = extract_rows_from_message(service, user_id, msg, cfg['decimal_comma'])
            all_rows.extend(rows)
            print(f"[INFO] {i}/{len(msg_ids)} msg={mid} rows={len(rows)}")
        except HttpError as e:
            print(f"[ERROR] Gmail get message failed: {e}", file=sys.stderr)

    if not all_rows:
        print("[INFO] Nothing to insert.")
        return

    df = pd.DataFrame(all_rows)
    # подстраховка от явных дублей в одном запуске
    df = df.drop_duplicates(subset=['row_hash'], keep='last')

    if dry_run:
        print(df.head(10).to_string(index=False))
        print(f"[INFO] DRY-RUN rows: {len(df)}")
        return

    client = ch_client(cfg)
    client.command("CREATE DATABASE IF NOT EXISTS zakaz")
    client.insert_df('zakaz.stg_mail_sales_raw', df)
    print(f"[INFO] Inserted rows: {len(df)}")

def main():
    parser = argparse.ArgumentParser(description="Ingest sales from Gmail to ClickHouse")
    parser.add_argument('--limit', type=int, default=None, help='Limit messages')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    cfg = load_env()
    ingest(cfg, limit=args.limit, dry_run=args.dry_run)

if __name__ == '__main__':
    main()