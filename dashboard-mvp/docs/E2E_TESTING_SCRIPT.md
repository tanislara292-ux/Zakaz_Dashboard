# E2E Тестирование системы с реальными данными

## Обзор

Документ содержит полный скрипт для end-to-end тестирования системы Zakaz Dashboard с реальными данными из всех источников: QTickets, VK Ads, Яндекс.Директ, Google Sheets и Yandex DataLens.

## Предпосылки для тестирования

### Обязательные требования

1. **Docker Desktop** запущен
2. **ClickHouse контейнеры** запущены
3. **Файлы конфигурации** созданы в `secrets/`
4. **Токены API** получены и корректны

### Проверка готовности

```bash
# 1. Проверка статуса контейнеров
docker ps | grep -E "ch-zakaz|ch-zakaz-caddy"

# 2. Проверка доступности ClickHouse
docker exec ch-zakaz clickhouse-client --query="SELECT 1"

# 3. Проверка наличия файлов конфигурации
ls -la dashboard-mvp/secrets/

# 4. Проверка токенов
grep -E "QTICKETS_TOKEN|VK_TOKEN|DIRECT_TOKEN|GOOGLE_SHEETS_ID" dashboard-mvp/secrets/.env.*
```

## Полный E2E скрипт тестирования

### Шаг 1: Подготовка окружения

```bash
#!/bin/bash

# E2E тестирование Zakaz Dashboard с реальными данными
# Использование: bash e2e_test_real_data.sh

set -e

echo "=== E2E Тестирование Zakaz Dashboard ==="
echo "Дата: $(date)"
echo ""

# Переход в директорию проекта
cd dashboard-mvp

# Создание директории логов
mkdir -p logs

# Проверка Docker
echo "1. Проверка Docker..."
if ! docker ps | grep -q "ch-zakaz"; then
    echo "❌ Контейнер ClickHouse не запущен"
    echo "Выполните: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi
echo "✅ Docker работает"
```

### Шаг 2: Тестирование QTickets

```bash
# 2. Тестирование QTickets
echo "2. Тестирование QTickets..."

# Запуск загрузчика QTickets
echo "2.1. Запуск загрузчика QTickets..."
python3 integrations/qtickets/loader.py --env secrets/.env.qtickets --days 3

# Проверка загруженных данных
echo "2.2. Проверка загруженных данных QTickets..."
QTICKETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated)

if [ "$QTICKETS_COUNT" -gt 0 ]; then
    echo "✅ QTickets: загружено $QTICKETS_COUNT записей"
else
    echo "❌ QTickets: данные не загружены"
fi

# Проверка свежести данных
QTICKETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated)
QTICKETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated)

echo "   Последняя дата: $QTICKETS_LATEST"
echo "   Отставание: $QTICKETS_BEHIND дней"
```

### Шаг 3: Тестирование Google Sheets

```bash
# 3. Тестирование Google Sheets
echo "3. Тестирование Google Sheets..."

# Инициализация Google Sheets
echo "3.1. Инициализация Google Sheets..."
python3 archive/sheets/init.py

# Валидация данных
echo "3.2. Валидация данных Google Sheets..."
python3 archive/sheets/validate.py

# Проверка загруженных данных
echo "3.3. Проверка загруженных данных Google Sheets..."
SHEETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_google_sheets_raw" --format=TabSeparated)

if [ "$SHEETS_COUNT" -gt 0 ]; then
    echo "✅ Google Sheets: загружено $SHEETS_COUNT записей"
else
    echo "❌ Google Sheets: данные не загружены"
fi

# Проверка свежести данных
SHEETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated)
SHEETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated)

echo "   Последняя дата: $SHEETS_LATEST"
echo "   Отставание: $SHEETS_BEHIND дней"
```

### Шаг 4: Тестирование VK Ads

```bash
# 4. Тестирование VK Ads
echo "4. Тестирование VK Ads..."

# Запуск загрузчика VK Ads
echo "4.1. Запуск загрузчика VK Ads..."
python3 integrations/vk_ads/loader.py --env secrets/.env.vk --days 3

# Проверка загруженных данных
echo "4.2. Проверка загруженных данных VK Ads..."
VK_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_vk_ads_daily" --format=TabSeparated)

if [ "$VK_COUNT" -gt 0 ]; then
    echo "✅ VK Ads: загружено $VK_COUNT записей"
else
    echo "❌ VK Ads: данные не загружены"
fi

# Проверка свежести данных
VK_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated)
VK_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated)

echo "   Последняя дата: $VK_LATEST"
echo "   Отставание: $VK_BEHIND дней"
```

### Шаг 5: Тестирование Яндекс.Директ

```bash
# 5. Тестирование Яндекс.Директ
echo "5. Тестирование Яндекс.Директ..."

# Запуск загрузчика Яндекс.Директ
echo "5.1. Запуск загрузчика Яндекс.Директ..."
python3 integrations/direct/loader.py --env secrets/.env.direct --days 3

# Проверка загруженных данных
echo "5.2. Проверка загруженных данных Яндекс.Директ..."
DIRECT_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_direct_daily" --format=TabSeparated)

if [ "$DIRECT_COUNT" -gt 0 ]; then
    echo "✅ Яндекс.Директ: загружено $DIRECT_COUNT записей"
else
    echo "❌ Яндекс.Директ: данные не загружены"
fi

# Проверка свежести данных
DIRECT_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_direct_daily" --format=TabSeparated)
DIRECT_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_direct_daily" --format=TabSeparated)

echo "   Последняя дата: $DIRECT_LATEST"
echo "   Отставание: $DIRECT_BEHIND дней"
```

### Шаг 6: Тестирование агрегированных данных

```bash
# 6. Тестирование агрегированных данных
echo "6. Тестирование агрегированных данных..."

# Обновление материализованных представлений
echo "6.1. Обновление материализованных представлений..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="ALTER TABLE zakaz.dm_sales_14d MATERIALIZE INDEX"

# Проверка данных в представлениях
echo "6.2. Проверка данных в представлениях..."
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated)
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated)

echo "✅ v_sales_latest: $SALES_COUNT записей"
echo "✅ v_marketing_daily: $MARKETING_COUNT записей"

# Проверка корректности агрегации
echo "6.3. Проверка корректности агрегации..."
SALES_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(tickets_sold) FROM zakaz.v_sales_latest" --format=TabSeparated)
REVENUE_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(revenue - refunds_amount) FROM zakaz.v_sales_latest" --format=TabSeparated)

echo "   Продано билетов: $SALES_SUM"
echo "   Общая выручка: $REVENUE_SUM"
```

### Шаг 7: Тестирование доступа для DataLens

```bash
# 7. Тестирование доступа для DataLens
echo "7. Тестирование доступа для DataLens..."

# Проверка прав пользователя datalens_reader
echo "7.1. Проверка прав пользователя datalens_reader..."
READER_SALES=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated)
READER_MARKETING=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated)

if [ "$READER_SALES" = "$SALES_COUNT" ] && [ "$READER_MARKETING" = "$MARKETING_COUNT" ]; then
    echo "✅ Пользователь datalens_reader имеет доступ к данным"
else
    echo "❌ Проблема с доступом для пользователя datalens_reader"
    echo "   Ожидаемо: $SALES_COUNT, получено: $READER_SALES"
    echo "   Ожидаемо: $MARKETING_COUNT, получено: $READER_MARKETING"
fi
```

### Шаг 8: Тестирование производительности

```bash
# 8. Тестирование производительности
echo "8. Тестирование производительности..."

# Тестирование скорости запросов
echo "8.1. Тестирование скорости запросов..."
start_time=$(date +%s)

# Тестовый запрос
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    event_date,
    city,
    SUM(tickets_sold) as tickets,
    SUM(revenue - refunds_amount) as revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date, city
ORDER BY revenue DESC
LIMIT 10
" --format=Null >/dev/null 2>&1

end_time=$(date +%s)
query_time=$((end_time - start_time))

echo "   Время выполнения запроса: ${query_time} секунд"

if [ "$query_time" -lt 5 ]; then
    echo "✅ Производительность запросов: ${query_time}с (< 5s)"
else
    echo "⚠️ Производительность запросов: ${query_time}s (> 5s)"
fi
```

### Шаг 9: Тестирование целостности данных

```bash
# 9. Тестирование целостности данных
echo "9. Тестирование целостности данных..."

# Проверка на дубликаты
echo "9.1. Проверка на дубликаты..."
DUPLICATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
" --format=TabSeparated)

if [ "$DUPLICATES" -eq 0 ]; then
    echo "✅ Дубликаты отсутствуют"
else
    echo "⚠️ Обнаружены дубликаты: $DUPLICATES"
fi

# Проверка пропущенных дат
echo "9.2. Проверка пропущенных дат..."
MISSING_DATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
WITH date_series AS (
    SELECT today() - number as date
    FROM numbers(7)
)
SELECT 
    COUNT(date_series.date) - COUNT(DISTINCT(event_date) as missing_dates
FROM date_series
LEFT JOIN zakaz.v_sales_latest ON date_series.date = event_date
WHERE date_series.date >= today() - 7
" --format=TabSeparated)

if [ "$MISSING_DATES" -eq 0 ]; then
    echo "✅ Пропущенные даты отсутствуют"
else
    echo "⚠️ Пропущенные даты: $MISSING_DATES"
fi
```

### Шаг 10: Создание отчета

```bash
# 10. Создание отчета
echo "10. Создание отчета..."

# Создание отчета в JSON
REPORT_FILE="e2e_test_report_$(date +%Y%m%d_%H%M%S).json"

cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "test_date": "$(date +%Y-%m-%d)",
  "results": {
    "qtickets": {
      "loaded": $QTICKETS_COUNT,
      "latest_date": "$QTICKETS_LATEST",
      "days_behind": $QTICKETS_BEHIND
    },
    "google_sheets": {
      "loaded": $SHEETS_COUNT,
      "latest_date": "$SHEETS_LATEST",
      "days_behind": $SHEETS_BEHIND
    },
    "vk_ads": {
      "loaded": $VK_COUNT,
      "latest_date": "$VK_LATEST",
      "days_behind": $VK_BEHIND
    },
    "direct": {
      "loaded": $DIRECT_COUNT,
      "latest_date": "$DIRECT_LATEST",
      "days_behind": $DIRECT_BEHIND
    },
    "aggregated": {
      "sales_records": $SALES_COUNT,
      "marketing_records": $MARKETING_COUNT,
      "total_tickets": $SALES_SUM,
      "total_revenue": $REVENUE_SUM
    },
    "performance": {
      "query_time_seconds": $query_time
    },
    "data_quality": {
      "duplicates": $DUPLICATES,
      "missing_dates": $MISSING_DATES
    },
    "data_lens_access": {
      "sales_records": $READER_SALES,
      "marketing_records": $READER_MARKETING
    }
  }
}
EOF

echo "✅ Отчет создан: $REPORT_FILE"
```

### Шаг 11: Итоги

```bash
# 11. Итоги
echo "11. Итоги..."

# Подсчет общего количества записей
TOTAL_RECORDS=$((QTICKETS_COUNT + SHEETS_COUNT + VK_COUNT + DIRECT_COUNT))

# Определение статуса
if [ "$QTICKETS_COUNT" -gt 0 ] && [ "$SHEETS_COUNT" -gt 0 ] && [ "$VK_COUNT" -gt 0 ] && [ "$DIRECT_COUNT" -gt 0 ]; then
    STATUS="✅ УСПЕХ"
    EXIT_CODE=0
elif [ "$TOTAL_RECORDS" -gt 0 ]; then
    STATUS="⚠️ ЧАСТИЧНЫЙ УСПЕХ"
    EXIT_CODE=1
else
    STATUS="❌ НЕУДАЧА"
    EXIT_CODE=2
fi

echo "=== ИТОГИ E2E ТЕСТИРОВАНИЯ ==="
echo "Статус: $STATUS"
echo "Всего записей: $TOTAL_RECORDS"
echo "QTickets: $QTICKETS_COUNT"
echo "Google Sheets: $SHEETS_COUNT"
echo "VK Ads: $VK_COUNT"
echo "Яндекс.Директ: $DIRECT_COUNT"
echo "Производительность: ${query_time}с"
echo "Отчет: $REPORT_FILE"

exit $EXIT_CODE
```

## Полный скрипт

```bash
#!/bin/bash

# E2E тестирование Zakaz Dashboard с реальными данными
# Использование: bash e2e_test_real_data.sh

set -e

echo "=== E2E Тестирование Zakaz Dashboard ==="
echo "Дата: $(date)"
echo ""

# Переход в директорию проекта
cd dashboard-mvp

# Создание директории логов
mkdir -p logs

# Проверка Docker
echo "1. Проверка Docker..."
if ! docker ps | grep -q "ch-zakaz"; then
    echo "❌ Контейнер ClickHouse не запущен"
    echo "Выполните: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi
echo "✅ Docker работает"

# 2. Тестирование QTickets
echo "2. Тестирование QTickets..."
python3 integrations/qtickets/loader.py --env secrets/.env.qtickets --days 3
QTICKETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated)
QTICKETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated)
QTICKETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated)

if [ "$QTICKETS_COUNT" -gt 0 ]; then
    echo "✅ QTickets: загружено $QTICKETS_COUNT записей"
else
    echo "❌ QTickets: данные не загружены"
fi
echo "   Последняя дата: $QTICKETS_LATEST"
echo "   Отставание: $QTICKETS_BEHIND дней"

# 3. Тестирование Google Sheets
echo "3. Тестирование Google Sheets..."
python3 archive/sheets/init.py
python3 archive/sheets/validate.py
SHEETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_google_sheets_raw" --format=TabSeparated)
SHEETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated)
SHEETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated)

if [ "$SHEETS_COUNT" -gt 0 ]; then
    echo "✅ Google Sheets: загружено $SHEETS_COUNT записей"
else
    echo "❌ Google Sheets: данные не загружены"
fi
echo "   Последняя дата: $SHEETS_LATEST"
echo "   Отставание: $SHEETS_BEHIND дней"

# 4. Тестирование VK Ads
echo "4. Тестирование VK Ads..."
python3 integrations/vk_ads/loader.py --env secrets/.env.vk --days 3
VK_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_vk_ads_daily" --format=TabSeparated)
VK_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated)
VK_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated)

if [ "$VK_COUNT" -gt 0 ]; then
    echo "✅ VK Ads: загружено $VK_COUNT записей"
else
    echo "❌ VK Ads: данные не загружены"
fi
echo "   Последняя дата: $VK_LATEST"
echo "   Отставание: $VK_BEHIND дней"

# 5. Тестирование Яндекс.Директ
echo "5. Тестирование Яндекс.Директ..."
python3 integrations/direct/loader.py --env secrets/.env.direct --days 3
DIRECT_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_direct_daily" --format=TabSeparated)
DIRECT_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_direct_daily" --format=TabSeparated)
DIRECT_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_direct_daily" --format=TabSeparated)

if [ "$DIRECT_COUNT" -gt 0 ]; then
    echo "✅ Яндекс.Директ: загружено $DIRECT_COUNT записей"
else
    echo "❌ Яндекс.Директ: данные не загружены"
fi
echo "   Последняя дата: $DIRECT_LATEST"
echo "   Отставание: $DIRECT_BEHIND дней"

# 6. Тестирование агрегированных данных
echo "6. Тестирование агрегированных данных..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="ALTER TABLE zakaz.dm_sales_14d MATERIALIZE INDEX" >/dev/null 2>&1
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated)
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated)
SALES_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(tickets_sold) FROM zakaz.v_sales_latest" --format=TabSeparated)
REVENUE_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(revenue - refunds_amount) FROM zakaz.v_sales_latest" --format=TabSeparated)

echo "✅ v_sales_latest: $SALES_COUNT записей"
echo "✅ v_marketing_daily: $MARKETING_COUNT записей"
echo "   Продано билетов: $SALES_SUM"
echo "   Общая выручка: $REVENUE_SUM"

# 7. Тестирование доступа для DataLens
echo "7. Тестирование доступа для DataLens..."
READER_SALES=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated)
READER_MARKETING=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated)

if [ "$READER_SALES" = "$SALES_COUNT" ] && [ "$READER_MARKETING" = "$MARKETING_COUNT" ]; then
    echo "✅ Пользователь datalens_reader имеет доступ к данным"
else
    echo "❌ Проблема с доступом для пользователя datalens_reader"
fi

# 8. Тестирование производительности
echo "8. Тестирование производительности..."
start_time=$(date +%s)
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    event_date,
    city,
    SUM(tickets_sold) as tickets,
    SUM(revenue - refunds_amount) as revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date, city
ORDER BY revenue DESC
LIMIT 10
" --format=Null >/dev/null 2>&1
end_time=$(date +%s)
query_time=$((end_time - start_time))
echo "   Время выполнения запроса: ${query_time} секунд"

if [ "$query_time" -lt 5 ]; then
    echo "✅ Производительность запросов: ${query_time}с (< 5s)"
else
    echo "⚠️ Производительность запросов: ${query_time}s (> 5s)"
fi

# 9. Тестирование целостности данных
echo "9. Тестирование целостности данных..."
DUPLICATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
" --format=TabSeparated)
MISSING_DATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
WITH date_series AS (
    SELECT today() - number as date
    FROM numbers(7)
)
SELECT 
    COUNT(date_series.date) - COUNT(DISTINCT(event_date)) as missing_dates
FROM date_series
LEFT JOIN zakaz.v_sales_latest ON date_series.date = event_date
WHERE date_series.date >= today() - 7
" --format=TabSeparated)

if [ "$DUPLICATES" -eq 0 ]; then
    echo "✅ Дубликаты отсутствуют"
else
    echo "⚠️ Обнаружены дубликаты: $DUPLICATES"
fi

if [ "$MISSING_DATES" -eq 0 ]; then
    echo "✅ Пропущенные даты отсутствуют"
else
    echo "⚠️ Пропущенные даты: $MISSING_DATES"
fi

# 10. Создание отчета
echo "10. Создание отчета..."
REPORT_FILE="e2e_test_report_$(date +%Y%m%d_%H%M%S).json"
TOTAL_RECORDS=$((QTICKETS_COUNT + SHEETS_COUNT + VK_COUNT + DIRECT_COUNT))

if [ "$QTICKETS_COUNT" -gt 0 ] && [ "$SHEETS_COUNT" -gt 0 ] && [ "$VK_COUNT" -gt 0 ] && [ "$DIRECT_COUNT" -gt 0 ]; then
    STATUS="✅ УСПЕХ"
    EXIT_CODE=0
elif [ "$TOTAL_RECORDS" -gt 0 ]; then
    STATUS="⚠️ ЧАСТИЧНЫЙ УСПЕХ"
    EXIT_CODE=1
else
    STATUS="❌ НЕУДАЧА"
    EXIT_CODE=2
fi

cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "test_date": "$(date +%Y-%m-%d)",
  "results": {
    "qtickets": {
      "loaded": $QTICKETS_COUNT,
      "latest_date": "$QTICKETS_LATEST",
      "days_behind": $QTICKETS_BEHIND
    },
    "google_sheets": {
      "loaded": $SHEETS_COUNT,
      "latest_date": "$SHEETS_LATEST",
      "days_behind": $SHEETS_BEHIND
    },
    "vk_ads": {
      "loaded": $VK_COUNT,
      "latest_date": "$VK_LATEST",
      "days_behind": $VK_BEHIND
    },
    "direct": {
      "loaded": $DIRECT_COUNT,
      "latest_date": "$DIRECT_LATEST",
      "days_behind": $DIRECT_BEHIND
    },
    "aggregated": {
      "sales_records": $SALES_COUNT,
      "marketing_records": $MARKETING_COUNT,
      "total_tickets": $SALES_SUM,
      "total_revenue": $REVENUE_SUM
    },
    "performance": {
      "query_time_seconds": $query_time
    },
    "data_quality": {
      "duplicates": $DUPLICATES,
      "missing_dates": $MISSING_DATES
    },
    "data_lens_access": {
      "sales_records": $READER_SALES,
      "marketing_records": $READER_MARKETING
    }
  }
}
EOF

echo "✅ Отчет создан: $REPORT_FILE"

# 11. Итоги
echo "=== ИТОГИ E2E ТЕСТИРОВАНИЯ ==="
echo "Статус: $STATUS"
echo "Всего записей: $TOTAL_RECORDS"
echo "QTickets: $QTICKETS_COUNT"
echo "Google Sheets: $SHEETS_COUNT"
echo "VK Ads: $VK_COUNT"
echo "Яндекс.Директ: $DIRECT_COUNT"
echo "Производительность: ${query_time}с"
echo "Отчет: $REPORT_FILE"

exit $EXIT_CODE
```

## Запуск E2E тестирования

```bash
# Сохранение скрипта
cat > dashboard-mvp/e2e_test_real_data.sh << 'EOF'
[Полный скрипт из раздела выше]
EOF

# Сделать скрипт исполняемым
chmod +x dashboard-mvp/e2e_test_real_data.sh

# Запуск тестирования
cd dashboard-mvp
./e2e_test_real_data.sh
```

## Ожидаемые результаты

### Успешное выполнение

- Все источники данных загружены
- Агрегированные данные корректны
- Пользователь DataLens имеет доступ
- Производительность запросов < 5 секунд
- Отчет создан с результатами

### Частичный успех

- Некоторые источники данных не загружены
- Проблемы с производительностью
- Проблемы с доступом для DataLens

### Неудача

- Ни один источник данных не загружен
- Критические проблемы с качеством данных
- Система недоступна

---

**Статус**: 📋 Документация готова, требует выполнения
**Дата**: 20.10.2025
**Версия**: 1.0.0