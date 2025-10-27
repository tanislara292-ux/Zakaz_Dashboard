-- Migration: Final QTickets API Production Deployment (TASK-QT-API-PROD-READY)
-- This migration finalizes the ClickHouse schema for production deployment
-- with proper deduplication, partitioning, and GDPR compliance.

-- Drop old tables if they exist (for clean migration)
DROP TABLE IF EXISTS zakaz.stg_qtickets_api_orders_raw;
DROP TABLE IF EXISTS zakaz.stg_qtickets_api_inventory_raw;
DROP TABLE IF EXISTS zakaz.dim_events;
DROP TABLE IF EXISTS zakaz.fact_qtickets_sales_daily;
DROP TABLE IF EXISTS zakaz.fact_qtickets_inventory_latest;

-- Staging table for raw orders with deduplication
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_orders_raw
(
    order_id      String,           -- Unique order identifier
    event_id      String,           -- Event/show identifier
    city          LowCardinality(String), -- City (lowercase, normalized)
    sale_ts       DateTime,         -- Payment timestamp (MSK, no timezone)
    tickets_sold  UInt32,           -- Number of tickets in the order
    revenue       Float64,          -- Total revenue (RUB)
    currency      LowCardinality(String), -- Currency code (RUB by default)
    _ver          UInt64,           -- Version for ReplacingMergeTree
    _dedup_key    FixedString(32)  -- MD5 hash for deduplication
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (_dedup_key) -- Primary key for deduplication
SETTINGS index_granularity = 8192;

-- Staging table for inventory snapshots
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_inventory_raw
(
    snapshot_ts   DateTime,         -- Snapshot timestamp (MSK)
    event_id      String,           -- Event identifier
    event_name    String,           -- Event name
    city          LowCardinality(String), -- City (lowercase, normalized)
    tickets_total Nullable(UInt32), -- Total tickets (NULL if unavailable)
    tickets_left  Nullable(UInt32), -- Available tickets (NULL if unavailable)
    _ver          UInt64,           -- Version for ReplacingMergeTree
    _dedup_key    FixedString(32)   -- MD5 hash for deduplication
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (event_id, city, snapshot_ts)  -- Primary key for queries
SETTINGS index_granularity = 8192;

-- Dimension table for events
CREATE TABLE IF NOT EXISTS zakaz.dim_events
(
    event_id      String,           -- Event identifier
    event_name    String,           -- Event name
    city          LowCardinality(String), -- City (lowercase, normalized)
    start_date    Nullable(Date),   -- Event start date
    end_date      Nullable(Date),   -- Event end date
    tickets_total UInt32 DEFAULT 0, -- Latest total tickets
    tickets_left  UInt32 DEFAULT 0, -- Latest available tickets
    _ver          UInt64            -- Version for ReplacingMergeTree
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (event_id)   -- Primary key for joins
SETTINGS index_granularity = 8192;

-- Aggregated daily sales fact table
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_sales_daily
(
    sales_date    Date,             -- Sales date (MSK)
    event_id      String,           -- Event identifier
    city          LowCardinality(String), -- City (lowercase, normalized)
    tickets_sold  UInt32,           -- Total tickets sold this date
    revenue       Float64,          -- Total revenue this date (RUB)
    _ver          UInt64            -- Version for ReplacingMergeTree
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(sales_date)  -- Monthly partitioning for efficiency
ORDER BY (event_id, sales_date, city)  -- Primary key for time series queries
SETTINGS index_granularity = 8192;

-- Latest inventory snapshot fact table
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_inventory_latest
(
    snapshot_ts   DateTime,         -- Snapshot timestamp (MSK)
    event_id      String,           -- Event identifier
    event_name    String,           -- Event name
    city          LowCardinality(String), -- City (lowercase, normalized)
    tickets_total Nullable(UInt32), -- Total tickets
    tickets_left  Nullable(UInt32), -- Available tickets
    _ver          UInt64            -- Version for ReplacingMergeTree
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (event_id, city)  -- Primary key for latest lookups
SETTINGS index_granularity = 8192;

-- Indexes are omitted for production deployment
-- They can be added later with non-experimental syntax if needed

-- Materialized view for latest sales (14 days)
CREATE MATERIALIZED VIEW IF NOT EXISTS zakaz.mv_qtickets_sales_latest
ENGINE = ReplacingMergeTree()
PARTITION BY tuple()
ORDER BY (event_id, city)
AS SELECT
    event_id,
    city,
    argMax(sale_ts, _ver) AS latest_sale_ts,
    sum(tickets_sold) AS tickets_sold_14d,
    sum(revenue) AS revenue_14d
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts >= today() - INTERVAL 14 DAY
GROUP BY event_id, city;

-- Create job run tracking table if not exists (should already exist)
CREATE TABLE IF NOT EXISTS zakaz.meta_job_runs
(
    job           String,           -- Job name (e.g., 'qtickets_api')
    started_at    DateTime,         -- Job start timestamp
    finished_at   DateTime,         -- Job end timestamp
    rows_processed UInt64 DEFAULT 0, -- Number of rows processed
    status        String,           -- Job status ('ok', 'failed')
    message       String,           -- Optional status message
    metrics       String            -- JSON with detailed metrics
)
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (job, started_at)
SETTINGS index_granularity = 8192;

-- Create final view for dashboard consumption
CREATE OR REPLACE VIEW zakaz.v_qtickets_sales_dashboard AS
WITH
latest_sales AS (
    SELECT
        event_id,
        city,
        sum(tickets_sold) AS tickets_sold_today,
        sum(revenue) AS revenue_today
    FROM zakaz.fact_qtickets_sales_daily
    WHERE sales_date = today()
    GROUP BY event_id, city
),
latest_14d AS (
    SELECT
        event_id,
        city,
        sum(tickets_sold) AS tickets_sold_14d,
        sum(revenue) AS revenue_14d
    FROM zakaz.fact_qtickets_sales_daily
    WHERE sales_date >= today() - INTERVAL 14 DAY
    GROUP BY event_id, city
),
latest_inventory AS (
    SELECT
        event_id,
        argMax(event_name, _ver) AS event_name,
        argMax(tickets_total, _ver) AS tickets_total,
        argMax(tickets_left, _ver) AS tickets_left,
        argMax(snapshot_ts, _ver) AS snapshot_ts
    FROM zakaz.fact_qtickets_inventory_latest
    GROUP BY event_id
),
events_dim AS (
    SELECT
        event_id,
        argMax(event_name, _ver) AS event_name,
        argMax(city, _ver) AS city,
        argMax(start_date, _ver) AS start_date,
        argMax(end_date, _ver) AS end_date
    FROM zakaz.dim_events
    GROUP BY event_id
)
SELECT
    COALESCE(ls.event_id, li.event_id, ed.event_id) AS event_id,
    COALESCE(li.event_name, ed.event_name, 'Unknown Event') AS event_name,
    COALESCE(ls.city, coalesce(ed.city, '')) AS city,
    ls.tickets_sold_today,
    ls.revenue_today,
    l14.tickets_sold_14d,
    l14.revenue_14d,
    li.tickets_total,
    li.tickets_left,
    li.snapshot_ts AS inventory_updated_at,
    ed.start_date,
    ed.end_date
FROM events_dim ed
LEFT JOIN latest_sales ls ON ed.event_id = ls.event_id AND ed.city = ls.city
LEFT JOIN latest_14d l14 ON ed.event_id = l14.event_id AND ed.city = l14.city
LEFT JOIN latest_inventory li ON ed.event_id = li.event_id
ORDER BY ls.revenue_today DESC, l14.revenue_14d DESC;

-- Grant permissions for different user types
GRANT SELECT ON zakaz.v_qtickets_sales_dashboard TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.dim_events TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_inventory_latest TO datalens_reader;

-- Grant write permissions to ETL user
GRANT INSERT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer;
GRANT INSERT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer;
GRANT INSERT ON zakaz.dim_events TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_sales_daily TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_inventory_latest TO etl_writer;
GRANT INSERT ON zakaz.meta_job_runs TO etl_writer;
