-- Migration: Primary QTickets API ingestion (TASK-QT-API-PRIMARY) - LOCAL VERSION
-- Creates staging tables, facts, and views used by the new integration.
-- Modified for local testing with zakaz_test database

CREATE TABLE IF NOT EXISTS zakaz_test.stg_qtickets_api_orders_raw
(
    sale_ts       DateTime,
    event_id      String,
    city          String,
    utm_source    String,
    utm_medium    String,
    utm_campaign  String,
    utm_content   String,
    utm_term      String,
    tickets_sold  UInt32,
    revenue       Float64,
    currency      LowCardinality(String),
    payload_json  String,
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

CREATE TABLE IF NOT EXISTS zakaz_test.fact_qtickets_sales_utm_daily
(
    sales_date    Date,
    event_id      String,
    city          String,
    utm_source    String,
    utm_medium    String,
    utm_campaign  String,
    utm_content   String,
    utm_term      String,
    tickets_sold  UInt32,
    revenue       Float64,
    _ver          UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (sales_date, event_id, city, utm_source, utm_campaign, utm_medium, utm_content, utm_term);

CREATE TABLE IF NOT EXISTS zakaz_test.plan_sales
(
    sales_date   Date,
    event_id     String,
    city         String,
    plan_tickets UInt32 DEFAULT 0,
    plan_revenue Float64 DEFAULT 0,
    _ver         UInt64,
    _loaded_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (sales_date, city, event_id);

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

CREATE OR REPLACE VIEW zakaz_test.v_qtickets_sales_utm_daily AS
SELECT
    sales_date AS d,
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
FROM zakaz_test.fact_qtickets_sales_utm_daily
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

CREATE OR REPLACE VIEW zakaz_test.v_plan_vs_fact AS
WITH fact AS (
    SELECT
        sales_date,
        event_id,
        city,
        sum(tickets_sold) AS fact_tickets,
        sum(revenue) AS fact_revenue
    FROM zakaz_test.fact_qtickets_sales_daily
    GROUP BY sales_date, event_id, city
),
plan AS (
    SELECT
        sales_date,
        event_id,
        city,
        plan_tickets,
        plan_revenue
    FROM zakaz_test.plan_sales
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
