-- Smoke-проверки для QTickets Google Sheets интеграции

-- 1) Проверка версии ClickHouse
SELECT version() AS clickhouse_version;

-- 2) Проверка существования таблиц qtickets_sheets
SHOW TABLES FROM zakaz LIKE 'qtickets_sheets%';

-- 3) Проверка наличия данных в стейджинг таблицах
SELECT 
    'stg_qtickets_sheets_raw' AS table_name,
    count() AS rows
FROM zakaz.stg_qtickets_sheets_raw

UNION ALL

SELECT 
    'stg_qtickets_sheets_events' AS table_name,
    count() AS rows
FROM zakaz.stg_qtickets_sheets_events

UNION ALL

SELECT 
    'stg_qtickets_sheets_inventory' AS table_name,
    count() AS rows
FROM zakaz.stg_qtickets_sheets_inventory

UNION ALL

SELECT 
    'stg_qtickets_sheets_sales' AS table_name,
    count() AS rows
FROM zakaz.stg_qtickets_sheets_sales;

-- 4) Проверка наличия данных в факт таблицах
SELECT 
    'dim_events' AS table_name,
    count() AS rows
FROM zakaz.dim_events

UNION ALL

SELECT 
    'fact_qtickets_inventory' AS table_name,
    count() AS rows
FROM zakaz.fact_qtickets_inventory

UNION ALL

SELECT 
    'fact_qtickets_sales' AS table_name,
    count() AS rows
FROM zakaz.fact_qtickets_sales;

-- 5) Проверка свежести данных
SELECT 
    source,
    table_name,
    latest_date,
    days_behind,
    total_rows
FROM zakaz.v_qtickets_freshness
ORDER BY days_behind DESC;

-- 6) Проверка корректности данных в продажах
SELECT 
    count() AS total_rows,
    countIf(date = '1970-01-01') AS invalid_dates,
    countIf(event_id = '') AS empty_event_id,
    countIf(city = '') AS empty_city,
    countIf(tickets_sold = 0) AS zero_tickets,
    countIf(revenue = 0) AS zero_revenue
FROM zakaz.fact_qtickets_sales;

-- 7) Проверка корректности данных в мероприятиях
SELECT 
    count() AS total_rows,
    countIf(event_id = '') AS empty_event_id,
    countIf(event_name = '') AS empty_event_name,
    countIf(city = '') AS empty_city,
    countIf(event_date = '1970-01-01') AS invalid_dates
FROM zakaz.dim_events;

-- 8) Проверка дедупликации в продажах
SELECT 
    count() AS total_rows,
    countDistinct(hash_low_card) AS unique_hashes,
    count() - countDistinct(hash_low_card) AS duplicates
FROM zakaz.fact_qtickets_sales;

-- 9) Топ городов по продажам за последние 7 дней
SELECT 
    city,
    sum(tickets_sold) AS total_tickets,
    sum(revenue) AS total_revenue
FROM zakaz.fact_qtickets_sales FINAL
WHERE date >= today() - 7
GROUP BY city 
ORDER BY total_revenue DESC 
LIMIT 20;

-- 10) Распределение продаж по датам за последние 30 дней
SELECT 
    date,
    count() AS rows,
    sum(tickets_sold) AS tickets,
    sum(revenue) AS revenue
FROM zakaz.fact_qtickets_sales FINAL
WHERE date >= today() - 30
GROUP BY date
ORDER BY date DESC
LIMIT 30;

-- 11) Проверка последних загруженных данных
SELECT 
    date,
    event_id,
    event_name,
    city,
    tickets_sold,
    revenue,
    _ver
FROM zakaz.fact_qtickets_sales FINAL
ORDER BY _ver DESC
LIMIT 10;

-- 12) Проверка инвентаря по мероприятиям
SELECT 
    event_id,
    city,
    tickets_total,
    tickets_left,
    tickets_total - tickets_left AS tickets_sold
FROM zakaz.fact_qtickets_inventory FINAL
ORDER BY tickets_sold DESC
LIMIT 20;

-- 13) Проверка метаданных запусков
SELECT 
    job,
    status,
    started_at,
    finished_at,
    rows_processed,
    message
FROM zakaz.meta_job_runs
WHERE job = 'qtickets_sheets'
ORDER BY started_at DESC
LIMIT 10;

-- 14) Статистика запусков за последние 7 дней
SELECT 
    status,
    count() AS runs,
    avg(rows_processed) AS avg_rows,
    max(started_at) AS last_run
FROM zakaz.meta_job_runs
WHERE job = 'qtickets_sheets' 
  AND started_at >= today() - 7
GROUP BY status;

-- 15) Проверка представлений BI
SELECT 
    'v_qtickets_sales_latest' AS view_name,
    count() AS rows
FROM zakaz.v_qtickets_sales_latest

UNION ALL

SELECT 
    'v_qtickets_sales_14d' AS view_name,
    count() AS rows
FROM zakaz.v_qtickets_sales_14d

UNION ALL

SELECT 
    'v_qtickets_inventory' AS view_name,
    count() AS rows
FROM zakaz.v_qtickets_inventory;

-- 16) Проверка целостности данных между стейджинг и факт таблицами
WITH stg_sales AS (
    SELECT 
        count() AS total_rows,
        sum(tickets_sold) AS total_tickets,
        sum(revenue) AS total_revenue
    FROM zakaz.stg_qtickets_sheets_sales FINAL
),
fact_sales AS (
    SELECT 
        count() AS total_rows,
        sum(tickets_sold) AS total_tickets,
        sum(revenue) AS total_revenue
    FROM zakaz.fact_qtickets_sales FINAL
)
SELECT 
    'stg_qtickets_sheets_sales' AS source,
    total_rows,
    total_tickets,
    total_revenue
FROM stg_sales

UNION ALL

SELECT 
    'fact_qtickets_sales' AS source,
    total_rows,
    total_tickets,
    total_revenue
FROM fact_sales;

-- 17) Проверка наличия пустых хэшей
SELECT 
    'fact_qtickets_sales' AS table_name,
    countIf(hash_low_card = '') AS empty_hashes,
    countIf(hash_low_card != '') AS valid_hashes
FROM zakaz.fact_qtickets_sales

UNION ALL

SELECT 
    'dim_events' AS table_name,
    countIf(hash_low_card = '') AS empty_hashes,
    countIf(hash_low_card != '') AS valid_hashes
FROM zakaz.dim_events;

-- 18) Проверка распределения по валютам
SELECT 
    currency,
    count() AS rows,
    sum(revenue) AS total_revenue
FROM zakaz.fact_qtickets_sales FINAL
GROUP BY currency
ORDER BY total_revenue DESC;

-- 19) Проверка аномальных значений в продажах
SELECT 
    countIf(tickets_sold > 10000) AS high_tickets,
    countIf(revenue > 1000000) AS high_revenue,
    countIf(refunds > revenue) AS high_refunds,
    countIf(date > today()) AS future_dates
FROM zakaz.fact_qtickets_sales FINAL;

-- 20) Проверка покрытия данных по городам
SELECT 
    count(DISTINCT city) AS total_cities,
    arrayJoin(groupArray(city)) AS cities
FROM zakaz.fact_qtickets_sales FINAL
ORDER BY cities;