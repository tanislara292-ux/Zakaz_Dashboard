-- Smoke checks for QTickets API ingestion (TASK-QT-API-PROD-READY)
-- These checks validate data quality and freshness after production deployment

-- Verify staging tables exist
SELECT
    'stg_qtickets_api_orders_raw' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'stg_qtickets_api_orders_raw';

SELECT
    'stg_qtickets_api_inventory_raw' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'stg_qtickets_api_inventory_raw';

-- Verify final production tables exist
SELECT
    'v_qtickets_sales_dashboard' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'v_qtickets_sales_dashboard';

-- Ensure fact tables exist
SELECT
    'fact_qtickets_sales_daily' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'fact_qtickets_sales_daily';

SELECT
    'fact_qtickets_sales_utm_daily' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'fact_qtickets_sales_utm_daily';

SELECT
    'fact_qtickets_inventory_latest' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'fact_qtickets_inventory_latest';

SELECT
    'plan_sales' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz'
  AND name = 'plan_sales';

-- Validate data quality constraints
SELECT
    count() AS negative_revenue_rows
FROM zakaz.fact_qtickets_sales_daily
WHERE revenue < 0;

SELECT
    count() AS negative_inventory_rows
FROM zakaz.fact_qtickets_inventory_latest
WHERE tickets_left < 0 OR tickets_total < 0;

-- Check for duplicates in staging table (should be minimal with _dedup_key)
SELECT
    _dedup_key,
    count() - 1 AS duplicate_count
FROM zakaz.stg_qtickets_api_orders_raw
GROUP BY _dedup_key
HAVING count() > 1
LIMIT 10;

-- Ensure recent data is available (freshness checks)
SELECT
    max(sales_date) AS max_sales_date,
    today() - max(sales_date) AS days_since_latest,
    count() AS total_sales_records
FROM zakaz.fact_qtickets_sales_daily
WHERE sales_date >= today() - INTERVAL 7 DAY;

SELECT
    max(snapshot_ts) AS max_inventory_snapshot,
    dateDiff('hour', max(snapshot_ts), now()) AS hours_since_snapshot,
    count() AS total_inventory_records
FROM zakaz.fact_qtickets_inventory_latest
WHERE snapshot_ts >= now() - INTERVAL 48 HOUR;

-- Check staging table for recent data (should have data from last 48 hours)
SELECT
    count() AS recent_orders_staging,
    min(sale_ts) AS oldest_order_ts,
    max(sale_ts) AS newest_order_ts
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts >= now() - INTERVAL 48 HOUR;

-- Verify job runs are being recorded
SELECT
    job,
    status,
    max(started_at) AS last_run,
    count() AS total_runs
FROM zakaz.meta_job_runs
WHERE job = 'qtickets_api'
  AND started_at >= now() - INTERVAL 7 DAY
GROUP BY job, status;

-- Test final dashboard view has data
SELECT
    count() AS dashboard_events,
    sum(revenue_today) AS total_revenue_today,
    sum(tickets_sold_today) AS total_tickets_today
FROM zakaz.v_qtickets_sales_dashboard
WHERE revenue_today > 0
   OR tickets_sold_today > 0;

-- UTM coverage on recent orders (last 7 days)
SELECT
    count() AS orders_last_7d,
    sum(utm_source = '' OR utm_source IS NULL) AS orders_without_utm,
    round(if(count() = 0, 0, orders_without_utm * 100.0 / count()), 2) AS pct_without_utm
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts >= now() - INTERVAL 7 DAY;

-- Plan vs fact sanity (last 30 days)
SELECT
    count() AS plan_rows_30d,
    sum(plan_revenue) AS plan_revenue_30d,
    sum(fact_revenue) AS fact_revenue_30d
FROM zakaz.v_plan_vs_fact
WHERE sales_date >= today() - 30;
