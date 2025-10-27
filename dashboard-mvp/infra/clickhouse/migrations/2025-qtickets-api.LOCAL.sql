-- Migration: Primary QTickets API ingestion (TASK-QT-API-PRIMARY) - LOCAL VERSION
-- Creates staging tables, facts, and views used by the new integration.
-- Modified for local testing with zakaz_test database

CREATE TABLE IF NOT EXISTS zakaz_test.stg_qtickets_api_orders_raw
(
    sale_ts       DateTime,
    event_id      String,
    city          String,
    tickets_sold  UInt32,
    revenue       Float64,
    currency      LowCardinality(String),
    _ver          UInt64,
    _dedup_key    FixedString(32)
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (_dedup_key);

CREATE TABLE IF NOT EXISTS zakaz_test.stg_qtickets_api_inventory_raw
(
    snapshot_ts   DateTime,
    event_id      String,
    event_name    String,
    city          String,
    tickets_total UInt32,
    tickets_left  UInt32,
    _ver          UInt64,
    _dedup_key    FixedString(32)
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (event_id, city);

CREATE TABLE IF NOT EXISTS zakaz_test.dim_events
(
    event_id      String,
    event_name    String,
    city          String,
    start_date    Nullable(Date),
    end_date      Nullable(Date),
    tickets_total UInt32 DEFAULT 0,
    tickets_left  UInt32 DEFAULT 0,
    _ver          UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (event_id);

CREATE TABLE IF NOT EXISTS zakaz_test.fact_qtickets_sales_daily
(
    sales_date   Date,
    event_id     String,
    city         String,
    tickets_sold UInt32,
    revenue      Float64,
    _ver         UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (event_id, sales_date);

CREATE TABLE IF NOT EXISTS zakaz_test.fact_qtickets_inventory_latest
(
    snapshot_ts   DateTime,
    event_id      String,
    event_name    String,
    city          String,
    tickets_total UInt32,
    tickets_left  UInt32,
    _ver          UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (event_id, city);

CREATE OR REPLACE VIEW zakaz_test.v_sales_latest AS
WITH latest_sales AS (
    SELECT
        event_id,
        city,
        sales_date,
        sum(tickets_sold) AS tickets_sold,
        sum(revenue) AS revenue
    FROM zakaz_test.fact_qtickets_sales_daily
    WHERE sales_date >= today() - 14
    GROUP BY event_id, city, sales_date
),
latest_inventory AS (
    SELECT
        event_id,
        city,
        argMax(event_name, _ver)    AS event_name,
        argMax(tickets_total, _ver) AS tickets_total,
        argMax(tickets_left, _ver)  AS tickets_left,
        argMax(snapshot_ts, _ver)   AS snapshot_ts
    FROM zakaz_test.fact_qtickets_inventory_latest
    GROUP BY event_id, city
),
latest_events AS (
    SELECT
        event_id,
        argMax(event_name, _ver) AS event_name,
        argMax(city, _ver)       AS city
    FROM zakaz_test.dim_events
    GROUP BY event_id
)
SELECT
    s.event_id,
    coalesce(latest_inventory.event_name, latest_events.event_name) AS event_name,
    s.city,
    s.sales_date,
    s.tickets_sold,
    s.revenue,
    latest_inventory.tickets_total,
    latest_inventory.tickets_left,
    latest_inventory.snapshot_ts
FROM latest_sales s
LEFT JOIN latest_inventory
    ON s.event_id = latest_inventory.event_id
   AND lowerUTF8(s.city) = lowerUTF8(latest_inventory.city)
LEFT JOIN latest_events
    ON s.event_id = latest_events.event_id;

CREATE OR REPLACE VIEW zakaz_test.v_sales_14d AS
WITH events_lookup AS (
    SELECT
        event_id,
        argMax(event_name, _ver) AS event_name,
        argMax(city, _ver)       AS city
    FROM zakaz_test.dim_events
    GROUP BY event_id
)
SELECT
    s.event_id,
    coalesce(e.event_name, '') AS event_name,
    s.city,
    sum(s.tickets_sold) AS tickets_sold,
    sum(s.revenue) AS revenue
FROM zakaz_test.fact_qtickets_sales_daily s
LEFT JOIN events_lookup e ON s.event_id = e.event_id
WHERE s.sales_date >= today() - 13
GROUP BY s.event_id, e.event_name, s.city;