-- Smoke checks for QTickets API ingestion (TASK-QT-API-PRIMARY) - LOCAL VERSION
-- Modified for local testing with zakaz_test database

-- Verify staging tables exist
SELECT
    'stg_qtickets_api_orders_raw' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz_test'
  AND name = 'stg_qtickets_api_orders_raw';

SELECT
    'stg_qtickets_api_inventory_raw' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz_test'
  AND name = 'stg_qtickets_api_inventory_raw';

-- Ensure fact tables exist
SELECT
    'fact_qtickets_sales_daily' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz_test'
  AND name = 'fact_qtickets_sales_daily';

SELECT
    'fact_qtickets_inventory_latest' AS table_name,
    count() AS table_exists
FROM system.tables
WHERE database = 'zakaz_test'
  AND name = 'fact_qtickets_inventory_latest';

-- Validate data quality constraints
SELECT
    count() AS negative_revenue_rows
FROM zakaz_test.fact_qtickets_sales_daily
WHERE revenue < 0;

SELECT
    count() AS negative_inventory_rows
FROM zakaz_test.fact_qtickets_inventory_latest
WHERE tickets_left < 0 OR tickets_total < 0;

-- Ensure recent data is available (relaxed for local testing)
SELECT
    max(sales_date) AS max_sales_date,
    today() - max(sales_date) AS days_since_latest
FROM zakaz_test.fact_qtickets_sales_daily;

SELECT
    max(snapshot_ts) AS max_inventory_snapshot,
    dateDiff('hour', max(snapshot_ts), now()) AS hours_since_snapshot
FROM zakaz_test.fact_qtickets_inventory_latest;