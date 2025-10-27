#!/usr/bin/env python3
"""Тестирование загрузки данных из Google Sheets в ClickHouse."""

import os
import sys
import csv
import requests
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корень проекта в путь
sys.path.append(str(Path(__file__).resolve().parents[0]))

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
    
    url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export"
    params = {
        "format": "csv",
        "gid": "0",  # Первый лист
    }
    
    try:
        print(f"📥 Загрузка данных из Google Sheets...")
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

def cleanup():
    """Очистка временных файлов."""
    try:
        if os.path.exists("temp_google_sheets.csv"):
            os.remove("temp_google_sheets.csv")
            print("🧹 Временный файл удален")
    except Exception as e:
        print(f"⚠️ Ошибка при удалении временного файла: {e}")

def main():
    """Главная функция."""
    print("=== Тестирование загрузки данных из Google Sheets ===")
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
        cleanup()
        return 1
    
    # Шаг 3: Загрузка в ClickHouse
    loaded_count = load_to_clickhouse(records)
    
    # Шаг 4: Проверка данных
    verify_count = verify_data()
    
    # Шаг 5: Очистка
    cleanup()
    
    print("")
    if loaded_count > 0 and verify_count > 0:
        print("✅ Тестирование успешно завершено")
        return 0
    else:
        print("❌ Тестирование завершилось с ошибками")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)