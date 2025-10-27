#!/bin/bash

# Скрипт для инициализации ClickHouse и загрузки тестовых данных для DataLens
# Использование: bash ops/init_clickhouse_for_datalens.sh

set -e

echo "=== Инициализация ClickHouse для DataLens ==="
echo "Дата: $(date)"
echo ""

# Проверка, что контейнеры запущены
echo "1. Проверка статуса контейнеров..."
if ! docker ps | grep -q "ch-zakaz"; then
    echo "❌ Контейнер ClickHouse не запущен"
    echo "Выполните: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q "ch-zakaz-caddy"; then
    echo "❌ Контейнер Caddy не запущен"
    echo "Выполните: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi

echo "✅ Контейнеры запущены"
echo ""

# Проверка доступности ClickHouse
echo "2. Проверка доступности ClickHouse..."
if docker exec ch-zakaz clickhouse-client --query="SELECT 1" >/dev/null 2>&1; then
    echo "✅ ClickHouse доступен"
else
    echo "❌ ClickHouse недоступен"
    exit 1
fi
echo ""

# Создание базы данных и пользователей
echo "3. Создание базы данных и пользователей..."
docker exec ch-zakaz clickhouse-client --query="
CREATE DATABASE IF NOT EXISTS zakaz;
" >/dev/null 2>&1

docker exec ch-zakaz clickhouse-client --query="
CREATE USER IF NOT EXISTS 'datalens_reader' IDENTIFIED BY 'DataLens2024!Strong#Pass';
" >/dev/null 2>&1

docker exec ch-zakaz clickhouse-client --query="
GRANT SELECT ON zakaz.* TO 'datalens_reader';
" >/dev/null 2>&1

echo "✅ База данных и пользователь созданы"
echo ""

# Создание таблиц
echo "4. Создание таблиц..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
-- Таблица с сырыми данными о продажах
CREATE TABLE IF NOT EXISTS stg_qtickets_sales_raw (
    src_msg_id String,                 -- для трассировки ('' для API)
    ingested_at DateTime DEFAULT now(),
    event_date Date,
    event_id String,
    event_name String,
    city String,
    tickets_sold Int32,
    revenue Float64,
    refunds Float64,
    currency LowCardinality(String),
    _ver DateTime                      -- версия строки (по времени приёма)
) ENGINE = ReplacingMergeTree(_ver)
ORDER BY (event_date, lowerUTF8(city), event_name);
" >/dev/null 2>&1

# Таблица с мероприятиями
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE TABLE IF NOT EXISTS dim_events (
    event_id String,
    event_name String,
    event_date Date,
    city String,
    tickets_total Int32,
    tickets_left Int32,
    _ver DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ver)
ORDER BY (event_date, event_id);
" >/dev/null 2>&1

# Таблица с маркетинговыми данными VK Ads
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE TABLE IF NOT EXISTS fact_vk_ads_daily (
    stat_date Date,
    account_id UInt64,
    campaign_id UInt64,
    ad_group_id UInt64,
    ad_id UInt64,
    impressions UInt64,
    clicks UInt64,
    spent Float64,
    utm_source String,
    utm_medium String,
    utm_campaign String,
    utm_content String,
    utm_city String,           -- из utm_content
    utm_day UInt8,
    utm_month UInt8,
    _ver DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ver)
ORDER BY (stat_date, account_id, campaign_id, ad_group_id, ad_id);
" >/dev/null 2>&1

echo "✅ Таблицы созданы"
echo ""

# Создание представлений
echo "5. Создание представлений..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
-- Актуалка без дублей
CREATE OR REPLACE VIEW v_sales_latest AS
SELECT
    event_date,
    city,
    argMax(event_id, _ver)      AS event_id,
    argMax(event_name, _ver)    AS event_name,
    argMax(tickets_sold, _ver)  AS tickets_sold,
    argMax(revenue, _ver)       AS revenue,
    argMax(refunds, _ver)       AS refunds,
    argMax(currency, _ver)      AS currency
FROM stg_qtickets_sales_raw
GROUP BY event_date, city, event_name;
" >/dev/null 2>&1

# Агрегированное представление за 14 дней для быстрых графиков
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE OR REPLACE VIEW v_sales_14d AS
SELECT
    toDate(event_date) AS d,
    city,
    event_name,
    sum(tickets_sold) AS tickets,
    sum(revenue)      AS revenue,
    sum(refunds)      AS refunds
FROM v_sales_latest
WHERE event_date >= today() - 14
GROUP BY d, city, event_name
ORDER BY d;
" >/dev/null 2>&1

# Сводка маркетинга по городам/дням
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE OR REPLACE VIEW v_marketing_daily AS
WITH mkt AS (
  SELECT
    d AS d,
    sum(spent) AS spend_total
  FROM (
    SELECT stat_date AS d, sum(spent) AS spend FROM fact_vk_ads_daily GROUP BY stat_date
  )
  GROUP BY d
),
sales AS (
  SELECT event_date AS d, sum(revenue - refunds) AS net_revenue
  FROM v_sales_latest
  GROUP BY d
)
SELECT
  s.d,
  s.net_revenue,
  m.spend_total,
  if(m.spend_total > 0, s.net_revenue / m.spend_total, null) AS romi
FROM sales s
LEFT JOIN mkt m USING(d)
ORDER BY d;
" >/dev/null 2>&1

echo "✅ Представления созданы"
echo ""

# Загрузка тестовых данных
echo "6. Загрузка тестовых данных..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
-- Тестовые данные о продажах
INSERT INTO stg_qtickets_sales_raw VALUES
    ('api_1', now(), today() - 7, 'Концерт 1', 'Москва', 100, 15000.0, 500.0, 'RUB', now()),
    ('api_2', now(), today() - 6, 'Концерт 2', 'Санкт-Петербург', 80, 12000.0, 300.0, 'RUB', now()),
    ('api_3', now(), today() - 5, 'Концерт 3', 'Москва', 120, 18000.0, 600.0, 'RUB', now()),
    ('api_4', now(), today() - 4, 'Концерт 4', 'Новосибирск', 60, 9000.0, 200.0, 'RUB', now()),
    ('api_5', now(), today() - 3, 'Концерт 5', 'Екатеринбург', 90, 13500.0, 450.0, 'RUB', now()),
    ('api_6', now(), today() - 2, 'Концерт 6', 'Москва', 110, 16500.0, 550.0, 'RUB', now()),
    ('api_7', now(), today() - 1, 'Концерт 7', 'Санкт-Петербург', 70, 10500.0, 350.0, 'RUB', now()),
    ('api_8', now(), today(), 'Концерт 8', 'Москва', 130, 19500.0, 650.0, 'RUB', now());
" >/dev/null 2>&1

docker exec ch-zakaz clickhouse-client --database=zakaz --query="
-- Тестовые данные о мероприятиях
INSERT INTO dim_events VALUES
    ('event_1', 'Концерт 1', today() - 7, 'Москва', 200, 100, now()),
    ('event_2', 'Концерт 2', today() - 6, 'Санкт-Петербург', 150, 70, now()),
    ('event_3', 'Концерт 3', today() - 5, 'Москва', 200, 80, now()),
    ('event_4', 'Концерт 4', today() - 4, 'Новосибирск', 100, 40, now()),
    ('event_5', 'Концерт 5', today() - 3, 'Екатеринбург', 150, 60, now()),
    ('event_6', 'Концерт 6', today() - 2, 'Москва', 200, 90, now()),
    ('event_7', 'Концерт 7', today() - 1, 'Санкт-Петербург', 150, 80, now()),
    ('event_8', 'Концерт 8', today(), 'Москва', 200, 70, now());
" >/dev/null 2>&1

docker exec ch-zakaz clickhouse-client --database=zakaz --query="
-- Тестовые маркетинговые данные
INSERT INTO fact_vk_ads_daily VALUES
    (today() - 7, 12345, 67890, 11111, 22222, 10000, 500, 5000.0, 'yandex', 'cpc', 'autumn', 'moscow_07_10', 'Москва', 7, 10, now()),
    (today() - 6, 12345, 67890, 11112, 22223, 8000, 400, 4000.0, 'yandex', 'cpc', 'autumn', 'spb_06_10', 'Санкт-Петербург', 6, 10, now()),
    (today() - 5, 12345, 67890, 11113, 22224, 12000, 600, 6000.0, 'yandex', 'cpc', 'autumn', 'moscow_05_10', 'Москва', 5, 10, now()),
    (today() - 4, 12345, 67890, 11114, 22225, 6000, 300, 3000.0, 'yandex', 'cpc', 'autumn', 'nsk_04_10', 'Новосибирск', 4, 10, now()),
    (today() - 3, 12345, 67890, 11115, 22226, 9000, 450, 4500.0, 'yandex', 'cpc', 'autumn', 'ekb_03_10', 'Екатеринбург', 3, 10, now()),
    (today() - 2, 12345, 67890, 11116, 22227, 11000, 550, 5500.0, 'yandex', 'cpc', 'autumn', 'moscow_02_10', 'Москва', 2, 10, now()),
    (today() - 1, 12345, 67890, 11117, 22228, 7000, 350, 3500.0, 'yandex', 'cpc', 'autumn', 'spb_01_10', 'Санкт-Петербург', 1, 10, now()),
    (today(), 12345, 67890, 11118, 22229, 13000, 650, 6500.0, 'yandex', 'cpc', 'autumn', 'moscow_08_10', 'Москва', 8, 10, now());
" >/dev/null 2>&1

echo "✅ Тестовые данные загружены"
echo ""

# Проверка данных
echo "7. Проверка данных..."
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated)
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated)

echo "✅ Проверка завершена"
echo "  Записей в v_sales_latest: $SALES_COUNT"
echo "  Записей в v_marketing_daily: $MARKETING_COUNT"
echo ""

# Проверка свежести данных
echo "8. Проверка свежести данных..."
LATEST_SALES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM v_sales_latest" --format=TabSeparated)
LATEST_MARKETING=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(d) FROM v_marketing_daily" --format=TabSeparated)

echo "✅ Свежесть данных:"
echo "  Последняя дата продаж: $LATEST_SALES"
echo "  Последняя дата маркетинга: $LATEST_MARKETING"
echo ""

# Проверка доступности для DataLens
echo "9. Проверка доступа для пользователя datalens_reader..."
READER_TEST=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated)

if [ "$READER_TEST" = "$SALES_COUNT" ]; then
    echo "✅ Пользователь datalens_reader имеет доступ к данным"
else
    echo "❌ Проблема с доступом для пользователя datalens_reader"
    echo "  Ожидаемое: $SALES_COUNT, получено: $READER_TEST"
fi
echo ""

# Рекомендации для DataLens
echo "10. Рекомендации для настройки DataLens:"
echo "   Хост: localhost"
echo "   Порт: 8080 (HTTP через Caddy) или 8123 (прямой доступ)"
echo "   База данных: zakaz"
echo "   Имя пользователя: datalens_reader"
echo "   Пароль: DataLens2024!Strong#Pass"
echo "   Использовать HTTPS: Нет (для локального тестирования)"
echo ""
echo "   SQL для источника данных продаж:"
echo "   SELECT"
echo "       event_date,"
echo "       city,"
echo "       event_name,"
echo "       tickets_sold,"
echo "       revenue,"
echo "       refunds_amount,"
echo "       (revenue - refunds_amount) AS net_revenue"
echo "   FROM zakaz.v_sales_latest"
echo ""
echo "   SQL для источника данных маркетинга:"
echo "   SELECT"
echo "       d,"
echo "       city,"
echo "       spend_total,"
echo "       net_revenue,"
echo "       romi"
echo "   FROM zakaz.v_marketing_daily"
echo ""

echo "=== Инициализация завершена ==="
echo "ClickHouse готов к подключению из DataLens"
echo ""