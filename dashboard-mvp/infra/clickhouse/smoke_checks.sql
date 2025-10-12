-- Smoke-проверки для ClickHouse после загрузки данных

-- 1) Проверка версии ClickHouse
SELECT version() AS clickhouse_version;

-- 2) Проверка существования таблиц
SHOW TABLES FROM zakaz;

-- 3) Есть ли данные в stg_qtickets_sales
SELECT count() AS rows FROM zakaz.stg_qtickets_sales;

-- 4) Оценка дублей по ключу
SELECT 
    count() AS total,
    countDistinct(dedup_key) AS uniq,
    count() - countDistinct(dedup_key) AS duplicates
FROM zakaz.stg_qtickets_sales;

-- 5) Снятие последней версии (FINAL)
SELECT count() AS final_rows FROM zakaz.stg_qtickets_sales FINAL;

-- 6) Топ по городам за последние 7 дней
SELECT 
    city,
    sum(tickets_sold) AS total_tickets,
    sum(revenue) AS total_revenue
FROM zakaz.stg_qtickets_sales FINAL
WHERE report_date >= today() - 7
GROUP BY city 
ORDER BY total_revenue DESC 
LIMIT 20;

-- 7) Распределение по датам отчета
SELECT 
    report_date,
    count() AS rows,
    sum(tickets_sold) AS tickets,
    sum(revenue) AS revenue
FROM zakaz.stg_qtickets_sales FINAL
GROUP BY report_date
ORDER BY report_date DESC
LIMIT 30;

-- 8) Проверка корректности данных (пропуски)
SELECT 
    count() AS total_rows,
    countIf(event_name = '') AS empty_event_name,
    countIf(city = '') AS empty_city,
    countIf(tickets_sold = 0) AS zero_tickets,
    countIf(revenue = 0) AS zero_revenue
FROM zakaz.stg_qtickets_sales FINAL;

-- 9) Статистика по суммам для проверки корректности загрузки денег
SELECT 
    min(revenue) AS min_revenue,
    max(revenue) AS max_revenue,
    avg(revenue) AS avg_revenue,
    sum(revenue) AS total_revenue
FROM zakaz.stg_qtickets_sales FINAL
WHERE revenue > 0;

-- 10) Проверка последних загруженных данных
SELECT 
    report_date,
    event_date,
    event_name,
    city,
    tickets_sold,
    revenue,
    ingested_at
FROM zakaz.stg_qtickets_sales FINAL
ORDER BY ingested_at DESC
LIMIT 10;

-- ========================================
-- EPIC-CH-03: ПРОВЕРКИ МАТЕРИАЛИЗОВАННЫХ ВИТРИН
-- ========================================

-- 11) Проверка наличия данных в dm_sales_daily
SELECT count() AS rows FROM zakaz.dm_sales_daily;

-- 12) Проверка наличия данных в dm_vk_ads_daily
SELECT count() AS rows FROM zakaz.dm_vk_ads_daily;

-- 13) Проверка наличия данных в stg_vk_ads_daily
SELECT count() AS rows FROM zakaz.stg_vk_ads_daily;

-- 14) Проверка справочника алиасов городов
SELECT count() AS rows FROM zakaz.dim_city_alias;

-- 15) Сверка агрегатов Sales: стейджинг vs витрина
SELECT
    'stg_qtickets_sales' AS source,
    sum(tickets_sold) AS total_tickets,
    sum(revenue) AS total_revenue,
    sum(refunds_amount) AS total_refunds
FROM zakaz.stg_qtickets_sales FINAL
WHERE event_date BETWEEN today() - 7 AND today()

UNION ALL

SELECT
    'dm_sales_daily' AS source,
    sum(tickets_sold) AS total_tickets,
    (sum(revenue) / 100) AS total_revenue,
    (sum(refunds_amount) / 100) AS total_refunds
FROM zakaz.dm_sales_daily
WHERE event_date BETWEEN today() - 7 AND today();

-- 16) Проверка сводной таблицы ROI
SELECT
    d,
    city,
    net_revenue,
    spend,
    tickets_sold,
    clicks,
    impressions,
    roas,
    cpc,
    cpt
FROM zakaz.v_marketing_roi_daily
WHERE d >= today() - 7
ORDER BY d DESC, net_revenue DESC
LIMIT 20;

-- 17) Проверка производительности витрины продаж
SELECT
    count() AS total_rows,
    min(event_date) AS min_date,
    max(event_date) AS max_date
FROM zakaz.v_dm_sales_daily;

-- 18) Проверка производительности витрины VK Ads
SELECT
    count() AS total_rows,
    min(stat_date) AS min_date,
    max(stat_date) AS max_date
FROM zakaz.v_vk_ads_daily;

-- 19) Проверка целостности данных в витрине VK Ads
SELECT
    stat_date,
    city,
    sum(impressions) AS impressions,
    sum(clicks) AS clicks,
    sum(spend) / 100 AS spend_rub
FROM zakaz.dm_vk_ads_daily
WHERE stat_date >= today() - 7
GROUP BY stat_date, city
ORDER BY stat_date DESC, spend_rub DESC
LIMIT 10;

-- 20) Проверка корректности конвертации валюты (в копейки)
SELECT
    min(spend) AS min_spend_kopecks,
    max(spend) AS max_spend_kopecks,
    sum(spend) / 100 AS total_spend_rub
FROM zakaz.dm_vk_ads_daily;

-- 21) Проверка отсутствия null значений в ключевых полях
SELECT
    countIf(stat_date IS NULL) AS null_dates,
    countIf(city = '') AS empty_cities,
    countIf(impressions = 0 AND clicks = 0 AND spend = 0) AS zero_metrics
FROM zakaz.dm_vk_ads_daily;

-- 22) Проверка версионности данных (_ver)
SELECT
    count() AS total_rows,
    countDistinct(_ver) AS unique_versions,
    min(_ver) AS min_ver,
    max(_ver) AS max_ver
FROM zakaz.dm_sales_daily

UNION ALL

SELECT
    count() AS total_rows,
    countDistinct(_ver) AS unique_versions,
    min(_ver) AS min_ver,
    max(_ver) AS max_ver
FROM zakaz.dm_vk_ads_daily;