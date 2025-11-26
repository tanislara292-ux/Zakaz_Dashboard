-- Migration: UTM enrichment + ROMI + plan tables
-- Adds UTM columns to QTickets orders, creates UTM sales fact, ROMI views, and plan table/view.

-- 1) Extend staging orders with UTM + payload
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS utm_source LowCardinality(String) AFTER city;
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS utm_medium LowCardinality(String) AFTER utm_source;
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS utm_campaign String AFTER utm_medium;
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS utm_content String AFTER utm_campaign;
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS utm_term String AFTER utm_content;
ALTER TABLE zakaz.stg_qtickets_api_orders_raw
    ADD COLUMN IF NOT EXISTS payload_json String AFTER currency;

-- 2) UTM-aware daily sales fact
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_sales_utm_daily
(
    sales_date    Date,
    event_id      String,
    city          LowCardinality(String),
    utm_source    LowCardinality(String),
    utm_medium    LowCardinality(String),
    utm_campaign  String,
    utm_content   String,
    utm_term      String,
    tickets_sold  UInt32,
    revenue       Float64,
    _ver          UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(sales_date)
ORDER BY (sales_date, event_id, city, utm_source, utm_campaign, utm_medium, utm_content, utm_term)
SETTINGS index_granularity = 8192;

-- 3) Marketing cost union + ROMI view
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

-- 4) Plan table + view
CREATE TABLE IF NOT EXISTS zakaz.plan_sales
(
    sales_date    Date,
    event_id      String,
    city          LowCardinality(String),
    plan_tickets  UInt32 DEFAULT 0,
    plan_revenue  Float64 DEFAULT 0,
    _ver          UInt64,
    _loaded_at    DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(sales_date)
ORDER BY (sales_date, city, event_id)
SETTINGS index_granularity = 8192;

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
