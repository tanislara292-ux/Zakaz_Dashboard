# Руководство по настройке Google Sheets как основного источника данных

## Обзор

Документ содержит пошаговые инструкции по настройке Google Sheets как основного источника данных для системы Zakaz Dashboard, обходя проблемы с QTickets API.

## Приоритет: Google Sheets > QTickets API

**Почему Google Sheets в приоритете:**
1. **Стабильность**: Google Sheets API стабилен и надежен
2. **Доступность**: Полностью доступен через публичный URL
3. **Данные**: Реальные данные без дублирования
4. **Простота**: Не требует сложной аутентификации

## Шаг 1: Проверка доступа к Google Sheets

### Тестирование доступа
```powershell
# Тестирование доступа к Google Sheets
$url = "https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc/export?format=csv"

try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing $false
    Write-Host "Доступ к Google Sheets"
    Write-Output $response.Content
} catch {
    Write-Host "Ошибка доступа к Google Sheets: $($_.Exception.Message)"
    Write-Output "Статус: $($response.StatusCode)"
}
```

### Ожидаемый результат
- **Статус**: 200 OK
- **Размер**: ~400KB данных
- **Формат**: CSV с данными о продажах

## Шаг 2: Создание рабочего загрузчика Google Sheets

### Создание файла конфигурации

Создайте `secrets/.env.sheets`:
```bash
# Google Sheets Configuration

# ID Google таблицы
GOOGLE_SHEETS_ID=1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc

# Email для доступа
GOOGLE_EMAIL=chufarovk@gmail.com

# Имя листа с данными
GOOGLE_SHEET_NAME=Лист1

# Диапазон данных
GOOGLE_RANGE=A:Z

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/sheets.log
```

### Создание загрузчика

Создайте `integrations/google_sheets/loader.py`:
```python
#!/usr/bin/env python3
"""Загрузчик данных из Google Sheets в ClickHouse."""

import os
import sys
import csv
import requests
from pathlib import Path
from dotenv import load_dotenv
from integrations.common import ClickHouseClient, get_client, now_msk, to_date

load_dotenv("secrets/.env.sheets")

# Конфигурация
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Лист1")
GOOGLE_RANGE = os.getenv("GOOGLE_RANGE", "A:Z")

def download_google_sheets_csv():
    """Загружает данные из Google Sheets в формате CSV."""
    if not GOOGLE_SHEETS_ID:
        print("❌ GOOGLE_SHEETS_ID не указан в secrets/.env.sheets")
        return None
    
    url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export?format=csv"
    params = {
        "format": "csv",
        "gid": "0",  # Первый лист
    }
    
    try:
        print("📥 Загрузка данных из Google Sheets...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Сохраняем во временный файл
        temp_file = "temp_google_sheets.csv"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"✅ Данные сохранены в {temp_file}")
        return temp_file
    except Exception as e:
        print(f"❌ Ошибка при загрузке данных: {e}")
        return None

def parse_csv_to_records(csv_file):
    """Парсит CSV файл в список записей."""
    records = []
    
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            print(f"📊 Найдены колонки: {headers}")
            
            for row in reader:
                # Пропускаем пустые строки
                if not any(row.values()):
                    continue
                
                # Преобразуем данные
                record = {}
                for header in headers:
                    value = row.get(header, "").strip()
                    record[header.lower().replace(" ", "_")] = value
                
                records.append(record)
        
        print(f"✅ Обработано {len(records)} записей")
        return records
    except Exception as e:
        print(f"❌ Ошибка при парсинге CSV: {e}")
        return []

def normalize_record(record):
    """Нормализует запись для вставки в ClickHouse."""
    try:
        # Извлечение UTM-меток
        utm_source = record.get("utm_source", "")
        utm_medium = record.get("utm_medium", "")
        utm_campaign = record.get("utm_campaign", "")
        utm_content = record.get("utm_content", "")
        utm_term = record.get("utm_term", "")
        
        # Дополнительный парсинг utm_content
        utm_city = ""
        utm_day = 0
        utm_month = 0
        
        if utm_content:
            parts = utm_content.split("_")
            if len(parts) >= 3:
                utm_city = parts[0]
                try:
                    utm_day = int(parts[1])
                    utm_month = int(parts[2])
                except ValueError:
                    pass
        
        return {
            "src_msg_id": f"gs_{now_msk().strftime('%Y%m%d_%H%M%S')}_{record.get('id', '')}",
            "ingested_at": now_msk(),
            "event_date": to_date(record.get("дата", "")),
            "city": record.get("город", "").strip().lower(),
            "event_name": record.get("название", "").strip(),
            "tickets_sold": int(record.get("продано", 0) or 0),
            "revenue": float(record.get("выручка", 0) or 0),
            "refunds_amount": float(record.get("возвраты", 0) or 0),
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_content": utm_content,
            "utm_term": utm_term,
            "utm_city": utm_city,
            "utm_day": utm_day,
            "utm_month": utm_month,
            "_ver": now_msk()
        }
    except Exception as e:
        print(f"❌ Ошибка при нормализации записи: {e}")
        return None

def load_to_clickhouse(records):
    """Загружает записи в ClickHouse."""
    if not records:
        print("❌ Нет записей для загрузки")
        return 0
    
    try:
        # Инициализация клиента ClickHouse
        ch_client = get_client("secrets/.env.sheets")
        
        # Нормализация данных
        normalized_records = []
        for record in records:
            normalized = normalize_record(record)
            if normalized:
                normalized_records.append(normalized)
        
        if not normalized_records:
            print("❌ Нет нормализованных записей для загрузки")
            return 0
        
        # Загрузка в ClickHouse
        print(f"💾 Загрузка {len(normalized_records)} записей в ClickHouse...")
        ch_client.insert("zakaz.stg_google_sheets_raw", normalized_records)
        
        print(f"✅ Успешно загружено {len(normalized_records)} записей")
        return len(normalized_records)
    except Exception as e:
        print(f"❌ Ошибка при загрузке в ClickHouse: {e}")
        return 0

def verify_data():
    """Проверяет загруженные данные."""
    try:
        ch_client = get_client("secrets/.env.sheets")
        
        count = ch_client.execute("SELECT count() FROM zakaz.stg_google_sheets_raw")
        latest = ch_client.execute("SELECT max(event_date) FROM zakaz.stg_google_sheets_raw")
        cities = ch_client.execute("SELECT countDistinct(city) FROM zakaz.stg_google_sheets_raw")
        
        print(f"📊 Проверка загруженных данных:")
        print(f"   Всего записей: {count}")
        print(f"   Последняя дата: {latest}")
        print(f"   Уникальных городов: {cities}")
        
        # Примеры данных
        sample = ch_client.execute("SELECT * FROM zakaz.stg_google_sheets_raw LIMIT 5")
        print(f"   Примеры данных:")
        for row in sample:
            print(f"     {row}")
        
        return count
    except Exception as e:
        print(f"❌ Ошибка при проверке данных: {e}")
        return 0

def main():
    """Главная функция."""
    print("=== Загрузка данных из Google Sheets ===")
    print(f"Дата: {now_msk()}")
    print("")
    
    # Шаг 1: Загрузка данных из Google Sheets
    csv_file = download_google_sheets_csv()
    if not csv_file:
        print("❌ Не удалось загрузить данные из Google Sheets")
        return 1
    
    # Шаг 2: Парсинг CSV
    records = parse_csv_to_records(csv_file)
    if not records:
        print("❌ Не удалось распарсить CSV файл")
        return 1
    
    # Шаг 3: Загрузка в ClickHouse
    loaded_count = load_to_clickhouse(records)
    
    # Шаг 4: Проверка данных
    verify_count = verify_data()
    
    print("")
    if loaded_count > 0 and verify_count > 0:
        print("✅ Загрузка успешно завершена")
        return 0
    else:
        print("❌ Загрузка завершилась с ошибками")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
```

## Шаг 3: Настройка автоматической загрузки

### Создание Systemd сервиса

Создайте `/etc/systemd/systemd/google-sheets.service`:
```ini
[Unit]
Description=Google Sheets Loader
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/zakaz-dashboard
ExecStart=/usr/bin/python3 /opt/zakaz-dashboard/integrations/google_sheets/loader.py
Environment=GOOGLE_SHEETS_ID=1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc
StandardOutput=journal
StandardError=journal
```

### Создание Systemd таймера

Создайте `/etc/systemd/systemd/google-sheets.timer`:
```ini
[Unit]
Description=Google Sheets Loader Timer
Requires=google-sheets.service

[Timer]
OnCalendar=daily
Persistent=true
Unit=google-sheets.service

[Install]
WantedBy=timers.target
```

### Активация сервисов

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Активация сервиса и таймера
sudo systemctl enable google-sheets.service
sudo systemctl enable google-sheets.timer
sudo systemctl start google-sheets.timer

# Проверка статуса
systemctl list-timers | grep google-sheets
```

## Шаг 4: Обновление представлений для DataLens

### Обновление представлений

```sql
-- Обновление представления для использования данных из Google Sheets
CREATE OR REPLACE VIEW v_sales_latest AS
SELECT
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    (revenue - refunds_amount) AS net_revenue
FROM (
    SELECT 
        event_date,
        city,
        event_name,
        tickets_sold,
        revenue,
        refunds_amount
    FROM zakaz.stg_google_sheets_raw
    
    UNION ALL
    
    SELECT 
        event_date,
        city,
        event_name,
        tickets_sold,
        revenue,
        refunds_amount
    FROM zakaz.stg_qtickets_sales_raw
)
ORDER BY event_date DESC;
```

## Шаг 5: Настройка DataLens

### Параметры подключения

```
Хост: localhost
Порт: 8123
База данных: zakaz
Пользователь: datalens_reader
Пароль: DataLens2024!Strong#Pass
HTTPS: Нет (для локального тестирования)
```

### SQL-запрос для DataLens

```sql
-- Источник продаж (Google Sheets + QTickets)
SELECT
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    (revenue - refunds_amount) AS net_revenue
FROM zakaz.v_sales_latest
ORDER BY event_date DESC;

-- Источник маркетинга (Google Sheets + VK Ads + Яндекс.Директ)
SELECT
    d,
    city,
    source,
    spend_total,
    net_revenue,
    romi
FROM zakaz.v_marketing_daily
ORDER BY d DESC;
```

## Шаг 6: Тестирование

### Тестирование загрузчика

```bash
# Тестирование загрузчика
cd /opt/zakaz-dashboard
python3 integrations/google_sheets/loader.py

# Проверка загруженных данных
docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.stg_google_sheets_raw"
```

### Тестирование представлений

```sql
-- Тестирование представлений
SELECT count() FROM zakaz.v_sales_latest;
SELECT count() FROM zakaz.v_marketing_daily;
```

## Шаг 7: Мониторинг

### Проверка логов

```bash
# Просмотр логов загрузки
tail -f /var/log/zakaz-dashboard/google-sheets.log

# Просмотр логов ошибок
journalctl -u google-sheets.service -n 20
```

### Проверка свежести данных

```sql
-- Проверка свежести данных
SELECT 
    'google_sheets' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.stg_google_sheets_raw

UNION ALL

SELECT 
    'qtickets' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.stg_qtickets_sales_raw;
```

## Проблемы и решения

### Проблема: Дубликаты данных

**Решение:**
```sql
-- Удаление дубликатов
ALTER TABLE zakaz.stg_google_sheets_raw DELETE WHERE src_msg_id IN (
    SELECT src_msg_id
    FROM (
        SELECT src_msg_id
        FROM zakaz.stg_google_sheets_raw
        GROUP BY src_msg_id
        HAVING count() > 1
    )
);
```

### Проблема: Пропущенные даты

**Решение:**
```sql
-- Поиск пропущенных дат
WITH date_series AS (
    SELECT today() - number as date
    FROM numbers(30)
)
SELECT 
    date_series.date
FROM date_series
LEFT JOIN zakaz.stg_google_sheets_raw ON date_series.date = event_date
WHERE zakaz.stg_google_sheets_raw.event_date IS NULL
ORDER BY date_series.date;
```

## Заключение

Google Sheets API полностью работает и может быть использован как основной источник данных для системы Zakaz Dashboard. Это позволяет обойти проблемы с QTickets API и обеспечить стабильную загрузку реальных данных.

---

**Статус руководства**: 📋 Готово к выполнению
**Дата создания**: 20.10.2025
**Версия**: 1.0.0