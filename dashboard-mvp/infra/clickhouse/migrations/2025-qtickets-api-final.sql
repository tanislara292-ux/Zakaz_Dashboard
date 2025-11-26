-- Migration: Final QTickets API Production Deployment (TASK-QT-API-PROD-READY)
-- This migration finalizes the ClickHouse schema for production deployment
-- with proper deduplication, partitioning, and GDPR compliance.

-- Drop old tables if they exist (for clean migration)
DROP TABLE IF EXISTS zakaz.stg_qtickets_api_orders_raw;
DROP TABLE IF EXISTS zakaz.stg_qtickets_api_inventory_raw;
DROP TABLE IF EXISTS zakaz.dim_events;
DROP TABLE IF EXISTS zakaz.fact_qtickets_sales_daily;
DROP TABLE IF EXISTS zakaz.fact_qtickets_sales_utm_daily;
DROP TABLE IF EXISTS zakaz.fact_qtickets_inventory_latest;
DROP TABLE IF EXISTS zakaz.plan_sales;

-- Staging table for raw orders with deduplication
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_orders_raw
(
    order_id      String,           -- Unique order identifier
    event_id      String,           -- Event/show identifier
    city          LowCardinality(String), -- City (lowercase, normalized)
    utm_source    LowCardinality(String), -- UTM source (empty when unknown)
    utm_medium    LowCardinality(String), -- UTM medium
    utm_campaign  String,           -- UTM campaign
    utm_content   String,           -- UTM content/raw tag
    utm_term      String,           -- UTM term/keyword
    sale_ts       DateTime,         -- Payment timestamp (MSK, no timezone)
    tickets_sold  UInt32,           -- Number of tickets in the order
    revenue       Float64,          -- Total revenue (RUB)
    currency      LowCardinality(String), -- Currency code (RUB by default)
    payload_json  String,           -- Full order payload for audits/backfills
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

-- Staging tables for auxiliary datasets (clients, discounts, partners)
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_clients_raw
(
    client_id    String,
    email        String,
    phone        String,
    first_name   String,
    last_name    String,
    middle_name  String,
    payload_json String,
    _ver         UInt64,
    _ingest_ts   DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (client_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_price_shades_raw
(
    shade_id     String,
    name         String,
    color        String,
    payload_json String,
    _ver         UInt64,
    _ingest_ts   DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (shade_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_discounts_raw
(
    discount_id   String,
    name          String,
    discount_type LowCardinality(String),
    discount_value Nullable(Float64),
    payload_json  String,
    _ver          UInt64,
    _ingest_ts    DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (discount_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_promo_codes_raw
(
    promo_code_id  String,
    code           String,
    discount_type  LowCardinality(String),
    discount_value Nullable(Float64),
    valid_from     Nullable(DateTime),
    valid_to       Nullable(DateTime),
    payload_json   String,
    _ver           UInt64,
    _ingest_ts     DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (promo_code_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_barcodes_raw
(
    barcode      String,
    event_id     String,
    show_id      String,
    status       LowCardinality(String),
    checked_at   Nullable(DateTime),
    payload_json String,
    _ver         UInt64,
    _ingest_ts   DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (barcode)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_partner_tickets_raw
(
    ticket_id         String,
    event_id          String,
    show_id           String,
    external_order_id String,
    external_id       String,
    barcode           String,
    paid              UInt8,
    price             Nullable(Float64),
    payload_json      String,
    _ver              UInt64,
    _ingest_ts        DateTime
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (ticket_id, external_order_id)
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
    _ver          UInt64,           -- Version for ReplacingMergeTree
    _loaded_at    DateTime DEFAULT now() -- Load timestamp
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

-- Aggregated daily sales fact table with UTM breakdown (for ROMI/attribution)
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_sales_utm_daily
(
    sales_date    Date,                    -- Sales date (MSK)
    event_id      String,                  -- Event identifier
    city          LowCardinality(String),  -- City (lowercase, normalized)
    utm_source    LowCardinality(String),  -- UTM source
    utm_medium    LowCardinality(String),  -- UTM medium
    utm_campaign  String,                  -- UTM campaign
    utm_content   String,                  -- UTM content/raw tag
    utm_term      String,                  -- UTM term/keyword
    tickets_sold  UInt32,                  -- Total tickets sold for this UTM
    revenue       Float64,                 -- Total revenue for this UTM (RUB)
    _ver          UInt64                   -- Version for ReplacingMergeTree
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(sales_date)
ORDER BY (sales_date, event_id, city, utm_source, utm_campaign, utm_medium, utm_content, utm_term)
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

-- Optional plan table for plan/fact dashboards
CREATE TABLE IF NOT EXISTS zakaz.plan_sales
(
    sales_date    Date,                    -- Planned sales date
    event_id      String,                  -- Event identifier
    city          LowCardinality(String),  -- City (lowercase, normalized)
    plan_tickets  UInt32 DEFAULT 0,        -- Planned tickets
    plan_revenue  Float64 DEFAULT 0,       -- Planned revenue (RUB)
    _ver          UInt64,                  -- Version for ReplacingMergeTree
    _loaded_at    DateTime DEFAULT now()   -- Load timestamp
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(sales_date)
ORDER BY (sales_date, city, event_id)
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

-- UTM-aware sales aggregation for ROMI/attribution
CREATE OR REPLACE VIEW zakaz.v_qtickets_sales_utm_daily AS
SELECT
    sales_date                           AS d,
    event_id,
    city,
    utm_source,
    utm_medium,
    utm_campaign,
    utm_content,
    utm_term,
    multiIf(
        utm_source = '' OR utm_source IS NULL, 'unknown',
        utm_source
    ) AS utm_group,
    sum(tickets_sold) AS tickets_sold,
    sum(revenue) AS revenue
FROM zakaz.fact_qtickets_sales_utm_daily
GROUP BY
    d,
    event_id,
    city,
    utm_source,
    utm_medium,
    utm_campaign,
    utm_content,
    utm_term,
    utm_group;

-- ROMI helper view: marketing spend union (VK + Direct)
CREATE OR REPLACE VIEW zakaz.v_marketing_costs_daily AS
SELECT
    stat_date AS d,
    'vk_ads' AS source,
    utm_source,
    utm_medium,
    utm_campaign,
    utm_content,
    utm_term,
    sum(spent) AS spend
FROM zakaz.fact_vk_ads_daily
GROUP BY d, source, utm_source, utm_medium, utm_campaign, utm_content, utm_term
UNION ALL
SELECT
    stat_date AS d,
    'direct' AS source,
    utm_source,
    utm_medium,
    utm_campaign,
    utm_content,
    utm_term,
    sum(cost) AS spend
FROM zakaz.fact_direct_daily
GROUP BY d, source, utm_source, utm_medium, utm_campaign, utm_content, utm_term;

-- ROMI view joining sales and spend on date + UTM
CREATE OR REPLACE VIEW zakaz.v_romi_daily AS
WITH sales AS (
    SELECT
        d,
        utm_source,
        utm_campaign,
        utm_medium,
        utm_content,
        utm_term,
        sum(revenue) AS revenue,
        sum(tickets_sold) AS tickets_sold
    FROM zakaz.v_qtickets_sales_utm_daily
    GROUP BY d, utm_source, utm_campaign, utm_medium, utm_content, utm_term
),
costs AS (
    SELECT
        d,
        utm_source,
        utm_campaign,
        utm_medium,
        utm_content,
        utm_term,
        sum(spend) AS spend
    FROM zakaz.v_marketing_costs_daily
    GROUP BY d, utm_source, utm_campaign, utm_medium, utm_content, utm_term
)
SELECT
    coalesce(s.d, c.d) AS d,
    coalesce(nullIf(s.utm_source, ''), nullIf(c.utm_source, ''), 'unknown') AS utm_source,
    coalesce(s.utm_campaign, c.utm_campaign, '') AS utm_campaign,
    coalesce(s.utm_medium, c.utm_medium, '') AS utm_medium,
    coalesce(s.utm_content, c.utm_content, '') AS utm_content,
    coalesce(s.utm_term, c.utm_term, '') AS utm_term,
    s.revenue,
    s.tickets_sold,
    c.spend,
    if(c.spend = 0, null, s.revenue / c.spend) AS roas
FROM sales s
FULL OUTER JOIN costs c
    ON s.d = c.d
   AND s.utm_source = c.utm_source
   AND s.utm_campaign = c.utm_campaign
   AND s.utm_medium = c.utm_medium
   AND s.utm_content = c.utm_content
   AND s.utm_term = c.utm_term;

-- Create job run tracking table if not exists (should already exist)
CREATE TABLE IF NOT EXISTS zakaz.meta_job_runs
(
    job              LowCardinality(String),     -- Название задачи
    run_id           UUID DEFAULT generateUUIDv4(), -- ID запуска
    started_at       DateTime,                  -- Время начала
    finished_at      DateTime,                  -- Время окончания
    status           LowCardinality(String),     -- Статус (ok, error, running)
    rows_processed   UInt64 DEFAULT 0,         -- Обработано строк
    message          String DEFAULT '',          -- Сообщение
    metrics          String DEFAULT ''           -- Метрики в JSON
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (job, started_at);

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

-- Plan vs fact helper view
CREATE OR REPLACE VIEW zakaz.v_plan_vs_fact AS
WITH fact AS (
    SELECT
        sales_date,
        event_id,
        city,
        sum(tickets_sold) AS fact_tickets,
        sum(revenue) AS fact_revenue
    FROM zakaz.fact_qtickets_sales_daily
    GROUP BY sales_date, event_id, city
),
plan AS (
    SELECT
        sales_date,
        event_id,
        city,
        plan_tickets,
        plan_revenue
    FROM zakaz.plan_sales
)
SELECT
    coalesce(f.sales_date, p.sales_date) AS sales_date,
    coalesce(f.event_id, p.event_id) AS event_id,
    coalesce(f.city, p.city) AS city,
    p.plan_tickets,
    p.plan_revenue,
    f.fact_tickets,
    f.fact_revenue,
    coalesce(f.fact_tickets, 0) - coalesce(p.plan_tickets, 0) AS diff_tickets,
    coalesce(f.fact_revenue, 0) - coalesce(p.plan_revenue, 0) AS diff_revenue,
    if(p.plan_revenue = 0, null, (f.fact_revenue - p.plan_revenue) / p.plan_revenue) AS diff_revenue_pct,
    if(p.plan_tickets = 0, null, (f.fact_tickets - p.plan_tickets) / p.plan_tickets) AS diff_tickets_pct
FROM plan p
FULL OUTER JOIN fact f
    ON p.sales_date = f.sales_date
   AND p.event_id = f.event_id
   AND p.city = f.city;
