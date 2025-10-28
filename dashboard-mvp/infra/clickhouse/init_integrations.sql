-- DDL для таблиц интеграций
-- База данных zakaz должна быть создана в основном init.sql

-- --- QTickets ---
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sales_raw
(
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
)
ENGINE = ReplacingMergeTree(_ver)
ORDER BY (event_date, lowerUTF8(city), event_name);

CREATE TABLE IF NOT EXISTS zakaz.dim_events
(
    event_id      String,                    -- Event identifier
    event_name    String,                    -- Event name
    city          LowCardinality(String),    -- City (lowercase, normalized)
    start_date    Nullable(Date),            -- Event start date
    end_date      Nullable(Date),            -- Event end date
    tickets_total UInt32 DEFAULT 0,          -- Latest total tickets
    tickets_left  UInt32 DEFAULT 0,          -- Latest available tickets
    _ver          UInt64,                    -- Version for ReplacingMergeTree
    _loaded_at    DateTime DEFAULT now()     -- Load timestamp
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (event_id)   -- Primary key for joins
SETTINGS index_granularity = 8192;

-- Актуалка без дублей
CREATE OR REPLACE VIEW zakaz.v_sales_latest AS
SELECT
  event_date,
  city,
  argMax(event_id, _ver)      AS event_id,
  argMax(event_name, _ver)    AS event_name,
  argMax(tickets_sold, _ver)  AS tickets_sold,
  argMax(revenue, _ver)       AS revenue,
  argMax(refunds, _ver)       AS refunds,
  argMax(currency, _ver)      AS currency
FROM zakaz.stg_qtickets_sales_raw
GROUP BY event_date, city, event_name;

-- --- VK Ads ---
CREATE TABLE IF NOT EXISTS zakaz.fact_vk_ads_daily
(
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
)
ENGINE = ReplacingMergeTree(_ver)
ORDER BY (stat_date, account_id, campaign_id, ad_group_id, ad_id);

-- --- Yandex Direct ---
CREATE TABLE IF NOT EXISTS zakaz.fact_direct_daily
(
  stat_date Date,
  account_login String,
  campaign_id UInt64,
  ad_group_id UInt64,
  ad_id UInt64,
  impressions UInt64,
  clicks UInt64,
  cost Float64,
  utm_source String,
  utm_medium String,
  utm_campaign String,
  utm_content String,
  utm_city String,
  utm_day UInt8,
  utm_month UInt8,
  _ver DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
ORDER BY (stat_date, account_login, campaign_id, ad_group_id, ad_id);

-- --- Сводка маркетинга по городам/дням ---
CREATE OR REPLACE VIEW zakaz.v_marketing_daily AS
WITH mkt AS (
  SELECT
    d AS d,
    sum(spend) AS spend_total
  FROM (
    SELECT stat_date AS d, sum(spent) AS spend FROM zakaz.fact_vk_ads_daily GROUP BY stat_date
    UNION ALL
    SELECT stat_date AS d, sum(cost)  AS spend FROM zakaz.fact_direct_daily GROUP BY stat_date
  )
  GROUP BY d
),
sales AS (
  SELECT event_date AS d, sum(revenue - refunds) AS net_revenue
  FROM zakaz.v_sales_latest
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

-- Последние 14 дней — для быстрых чартов
CREATE OR REPLACE VIEW zakaz.v_sales_14d AS
SELECT event_date AS d,
       sum(tickets_sold) AS tickets,
       sum(revenue - refunds) AS net_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 14
GROUP BY d
ORDER BY d;

-- Таблица для метаданных о запусках задач
CREATE TABLE IF NOT EXISTS zakaz.meta_job_runs
(
    job              LowCardinality(String),     -- Название задачи
    run_id           UUID DEFAULT generateUUIDv4(), -- ID запуска
    started_at       DateTime,                  -- Время начала
    finished_at      DateTime,                  -- Время окончания
    status           LowCardinality(String),     -- Статус (success, error, running)
    rows_processed   UInt64 DEFAULT 0,         -- Обработано строк
    message          String DEFAULT '',          -- Сообщение
    metrics          String DEFAULT ''           -- Метрики в JSON
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (job, started_at);

-- Таблица для алертов
CREATE TABLE IF NOT EXISTS zakaz.alerts
(
  alert_id UUID DEFAULT generateUUIDv4(),
  created_at DateTime DEFAULT now(),
  job String,
  alert_type LowCardinality(String),  -- error, warning, info
  title String,
  message String,
  details String,
  acknowledged Bool DEFAULT false,
  acknowledged_at DateTime,
  acknowledged_by String
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (job, created_at);

-- Вьюхи для мониторинга свежести данных
CREATE OR REPLACE VIEW zakaz.v_data_freshness AS
SELECT
  'qtickets_sales' as source,
  max(event_date) as latest_date,
  today() - max(event_date) as days_behind,
  count() as total_rows
FROM zakaz.v_sales_latest

UNION ALL

SELECT
  'vk_ads' as source,
  max(stat_date) as latest_date,
  today() - max(stat_date) as days_behind,
  count() as total_rows
FROM zakaz.fact_vk_ads_daily

UNION ALL

SELECT
  'direct' as source,
  max(stat_date) as latest_date,
  today() - max(stat_date) as days_behind,
  count() as total_rows
FROM zakaz.fact_direct_daily;

-- Вьюха для ROMI KPI
CREATE OR REPLACE VIEW zakaz.v_romi_kpi AS
SELECT
  d,
  net_revenue,
  spend_total,
  romi,
  CASE 
    WHEN romi > 1.5 THEN 'green'
    WHEN romi >= 1 AND romi <= 1.5 THEN 'yellow'
    WHEN romi < 1 OR romi IS NULL THEN 'red'
  END as romi_status
FROM zakaz.v_marketing_daily
WHERE d >= today() - 30;

-- Вьюха для агрегации продаж по городам
CREATE OR REPLACE VIEW zakaz.v_sales_by_city AS
SELECT
  city,
  sum(tickets_sold) as total_tickets,
  sum(revenue - refunds) as net_revenue,
  avg(tickets_sold) as avg_tickets_per_day,
  count() as days_with_sales
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 30
GROUP BY city
ORDER BY net_revenue DESC;

-- Вьюха для анализа эффективности рекламных кампаний
CREATE OR REPLACE VIEW zakaz.v_campaign_performance AS
WITH vk_campaigns AS (
  SELECT
    utm_campaign,
    utm_city,
    sum(impressions) as impressions,
    sum(clicks) as clicks,
    sum(spent) as spend,
    if(sum(clicks) > 0, sum(clicks) / sum(impressions), 0) as ctr,
    if(sum(clicks) > 0, sum(spent) / sum(clicks), 0) as cpc
  FROM zakaz.fact_vk_ads_daily
  WHERE stat_date >= today() - 30
  GROUP BY utm_campaign, utm_city
),
direct_campaigns AS (
  SELECT
    utm_campaign,
    utm_city,
    sum(impressions) as impressions,
    sum(clicks) as clicks,
    sum(cost) as spend,
    if(sum(clicks) > 0, sum(clicks) / sum(impressions), 0) as ctr,
    if(sum(clicks) > 0, sum(cost) / sum(clicks), 0) as cpc
  FROM zakaz.fact_direct_daily
  WHERE stat_date >= today() - 30
  GROUP BY utm_campaign, utm_city
),
sales_by_campaign AS (
  SELECT
    splitByString('_', utm_content)[1] as city,
    splitByString('_', utm_content)[2] as day,
    splitByString('_', utm_content)[3] as month,
    sum(revenue - refunds) as net_revenue
  FROM zakaz.v_sales_latest
  WHERE event_date >= today() - 30
  GROUP BY city, day, month
)
SELECT
  coalesce(vk.utm_campaign, d.utm_campaign) as campaign,
  coalesce(vk.utm_city, d.utm_city) as city,
  coalesce(vk.impressions, 0) + coalesce(d.impressions, 0) as impressions,
  coalesce(vk.clicks, 0) + coalesce(d.clicks, 0) as clicks,
  coalesce(vk.spend, 0) + coalesce(d.spend, 0) as spend,
  if((coalesce(vk.clicks, 0) + coalesce(d.clicks, 0)) > 0, 
     (coalesce(vk.clicks, 0) + coalesce(d.clicks, 0)) / (coalesce(vk.impressions, 0) + coalesce(d.impressions, 0)), 0) as ctr,
  if((coalesce(vk.clicks, 0) + coalesce(d.clicks, 0)) > 0, 
     (coalesce(vk.spend, 0) + coalesce(d.spend, 0)) / (coalesce(vk.clicks, 0) + coalesce(d.clicks, 0)), 0) as cpc,
  s.net_revenue,
  if((coalesce(vk.spend, 0) + coalesce(d.spend, 0)) > 0, 
     s.net_revenue / (coalesce(vk.spend, 0) + coalesce(d.spend, 0)), null) as romi
FROM vk_campaigns vk
FULL OUTER JOIN direct_campaigns d ON vk.utm_campaign = d.utm_campaign AND vk.utm_city = d.utm_city
LEFT JOIN sales_by_campaign s ON lower(coalesce(vk.utm_city, d.utm_city)) = lower(s.city)
ORDER BY romi DESC NULLS LAST;