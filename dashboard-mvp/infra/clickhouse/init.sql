-- РЎРѕР·РґР°РЅРёРµ Р‘Р” zakaz (РµСЃР»Рё РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚)
CREATE DATABASE IF NOT EXISTS zakaz;

-- РЎС‚РµР№РґР¶РёРЅРі вЂ” Р·Р°РєР°Р·С‹ QTickets
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sales
(
    report_date      Date,
    event_date       Date,
    event_id         String,
    event_name       String,
    city             String,
    tickets_sold     UInt32,
    revenue          Decimal(12,2),
    refunds_amount   Decimal(12,2) DEFAULT 0,
    currency         FixedString(3),

    src_message_id   String,
    src_message_ts   DateTime,
    dedup_key        String,            -- "<report_date>|<event_date>|<event_id>|<event_name>|<city>" (lower-case)
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (report_date, event_date, event_id, city, event_name);

-- Removed duplicate stg_vk_ads_daily definition - using canonical version later in file

-- РљР°СЂРєР°СЃ СЏРґСЂР° вЂ” С„Р°РєС‚РѕРІР°СЏ С‚Р°Р±Р»РёС†Р° РїСЂРѕРґР°Р¶ (РїРѕРєР° РїСѓСЃС‚Р°СЏ Р»РѕРіРёРєР°, С‚РѕР»СЊРєРѕ DDL)
CREATE TABLE IF NOT EXISTS zakaz.core_sales_fct
(
    sale_date     Date,
    event_date    Date,
    event_id      String,
    event_name    String,
    city          String,
    tickets_sold  UInt32,
    revenue       Decimal(12,2),
    refunds_amount   Decimal(12,2),
    currency      FixedString(3),
    load_ts       DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (sale_date, event_date, event_id, city, event_name);

-- РџСЂРµРґСЃС‚Р°РІР»РµРЅРёСЏ РґР»СЏ DataLens (BI-СЃР»РѕР№ Р±РµР· РґСѓР±Р»РµР№)
-- 2.1. РџСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ РїРѕ РїСЂРѕРґР°Р¶Р°Рј (Р±РµР· РґСѓР±Р»РµР№)
CREATE OR REPLACE VIEW zakaz.v_sales_latest AS
SELECT
    report_date       AS sale_date,
    event_date,
    event_id,
    event_name,
    city,
    tickets_sold,
    revenue,
    refunds_amount,
    currency
FROM zakaz.stg_qtickets_sales FINAL;

-- 2.2. РЈРєСЂСѓРїРЅРµРЅРёРµ В«Р·Р° 14 РґРЅРµР№В» (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ вЂ” РґР»СЏ Р±С‹СЃС‚СЂС‹С… РіСЂР°С„РёРєРѕРІ)
CREATE OR REPLACE VIEW zakaz.v_sales_14d AS
SELECT
    toDate(event_date) AS d,
    city,
    event_id,
    event_name,
    sum(tickets_sold) AS tickets_sold,
    sum(revenue)      AS revenue,
    sum(refunds_amount) AS refunds_amount
FROM zakaz.stg_qtickets_sales FINAL
WHERE report_date >= today() - 14
GROUP BY d, city, event_id, event_name;


-- ========================================
-- EPIC-CH-03: РњРђРўР•Р РРђР›РР—РћР’РђРќРќР«Р• Р’РРўР РРќР«
-- ========================================

-- 1.1 РњР°С‚РµСЂРёР°Р»РёР·РѕРІР°РЅРЅР°СЏ РІРёС‚СЂРёРЅР° РїСЂРѕРґР°Р¶
CREATE TABLE IF NOT EXISTS zakaz.dm_sales_daily
(
    event_date      Date,
    sale_date       Date,
    event_id        LowCardinality(String),
    city            LowCardinality(String),
    event_name      String,
    tickets_sold    UInt64,
    revenue         UInt64,
    refunds_amount  UInt64,
    net_revenue     Int64,
    currency        LowCardinality(String) DEFAULT 'RUB',
    _loaded_at      DateTime DEFAULT now(),
    _ver            UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, city, event_id, event_name);

-- 1.2 РџСЂРѕСЃР»РѕР№РєР° РґР»СЏ BI (РїР»РѕСЃРєРѕРµ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ)
CREATE OR REPLACE VIEW zakaz.v_dm_sales_daily AS
SELECT
    event_date,
    sale_date,
    event_id,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    net_revenue,
    currency,
    _loaded_at
FROM zakaz.dm_sales_daily;

-- 2.1 РЎС‚РµР№РґР¶ VK Ads (СЃС‹СЂС‹Рµ СЃСѓС‚РѕС‡РЅС‹Рµ Р°РіСЂРµРіР°С†РёРё)
-- РћР±РЅРѕРІР»СЏРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ С‚Р°Р±Р»РёС†Сѓ СЃ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹РјРё РїРѕР»СЏРјРё
-- Removed duplicate stg_vk_ads_daily definition - using canonical version later in file

-- 2.2 РЎРїСЂР°РІРѕС‡РЅРёРє Р°Р»РёР°СЃРѕРІ РіРѕСЂРѕРґРѕРІ (РєР°РЅРѕРЅРёР·Р°С†РёСЏ)
CREATE TABLE IF NOT EXISTS zakaz.dim_city_alias
(
    alias  LowCardinality(String),
    city   LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY (alias);

-- 2.3 Р•Р¶РµРґРЅРµРІРЅР°СЏ РІРёС‚СЂРёРЅР° VK Ads
CREATE TABLE IF NOT EXISTS zakaz.dm_vk_ads_daily
(
    stat_date   Date,
    city        LowCardinality(String),
    impressions UInt64,
    clicks      UInt64,
    spend       UInt64,
    _loaded_at  DateTime DEFAULT now(),
    _ver        UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(stat_date)
ORDER BY (stat_date, city);

-- 2.4 РџСЂРµРґСЃС‚Р°РІР»РµРЅРёСЏ РґР»СЏ BI
CREATE OR REPLACE VIEW zakaz.v_vk_ads_daily AS
SELECT stat_date, city, impressions, clicks, spend
FROM zakaz.dm_vk_ads_daily;

-- 2.5 РЎРІРѕРґРЅР°СЏ ROI (С‚РѕР»СЊРєРѕ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ, Р±РµР· С…СЂР°РЅРµРЅРёСЏ)
CREATE OR REPLACE VIEW zakaz.v_marketing_roi_daily AS
SELECT
    s.event_date                   AS d,
    s.city                         AS city,
    sum(s.net_revenue)             AS net_revenue,
    sum(s.tickets_sold)            AS tickets_sold,
    sum(v.spend)                   AS spend,
    sum(v.clicks)                  AS clicks,
    sum(v.impressions)             AS impressions,
    -- РїСЂРѕСЃС‚РµР№С€РёРµ РїРѕРєР°Р·Р°С‚РµР»Рё
    if(sum(v.spend)=0, 0, sum(s.net_revenue) / sum(v.spend)) AS roas,
    if(sum(v.clicks)=0, 0, sum(v.spend) / sum(v.clicks))     AS cpc,
    if(sum(s.tickets_sold)=0, 0, sum(v.spend)/sum(s.tickets_sold)) AS cpt
FROM zakaz.dm_sales_daily AS s
LEFT JOIN zakaz.dm_vk_ads_daily AS v
    ON v.stat_date = s.event_date
   AND v.city = s.city
GROUP BY d, city;

-- ========================================
-- EPIC-CH-04: ETL РћР РљР•РЎРўР РђР¦РРЇ Р РњРћРќРРўРћР РРќР“
-- ========================================

-- РЎРѕР·РґР°РЅРёРµ СЃС…РµРјС‹ meta, РµСЃР»Рё РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚
CREATE DATABASE IF NOT EXISTS meta;

-- 1.1 СЂРµРµСЃС‚СЂ РїСЂРѕРіРѕРЅРѕРІ ETL
CREATE TABLE IF NOT EXISTS meta.etl_runs
(
    job            LowCardinality(String),
    run_id         UUID,
    started_at     DateTime,
    finished_at    DateTime,
    status         LowCardinality(String),  -- 'ok' | 'error'
    rows_written   UInt64,
    rows_read      UInt64,
    err_msg        String,
    from_date      Date,
    to_date        Date,
    host           String,
    version_tag    String
)
ENGINE = MergeTree
ORDER BY (started_at, job)
PARTITION BY toYYYYMM(started_at);

-- 1.2 СЂРµРµСЃС‚СЂ Р°Р»РµСЂС‚РѕРІ
CREATE TABLE IF NOT EXISTS meta.etl_alerts
(
    ts            DateTime,
    severity      LowCardinality(String),  -- 'warning' | 'critical'
    job           LowCardinality(String),
    code          LowCardinality(String),  -- 'RUN_FAILED' | 'ZERO_ROWS' | 'ANOMALY' | ...
    message       String,
    context_json  String
)
ENGINE = MergeTree
ORDER BY ts
PARTITION BY toYYYYMM(ts);

-- 1.3 Р±С‹СЃС‚СЂС‹Рµ РїСЂРѕРІРµСЂРєРё РєР°С‡РµСЃС‚РІР° РїРѕСЃР»РµРґРЅРµРіРѕ РґРЅСЏ
CREATE OR REPLACE VIEW meta.v_quality_last_day AS
SELECT
    today() - 1 AS d,
    (SELECT count() FROM zakaz.dm_sales_daily WHERE event_date = today() - 1)          AS sales_rows,
    (SELECT sum(net_revenue) FROM zakaz.dm_sales_daily WHERE event_date = today() - 1) AS sales_revenue,
    (SELECT count() FROM zakaz.dm_vk_ads_daily WHERE stat_date = today() - 1)          AS vk_rows,
    (SELECT sum(spend) FROM zakaz.dm_vk_ads_daily WHERE stat_date = today() - 1)       AS vk_spend;


-- ========================================
-- EPIC-CH-06: РРќРљР Р•РњР•РќРўРђР›Р¬РќР«Р• CDC-Р—РђР“Р РЈР—РљР Р NRT
-- ========================================

-- 1. РўР°Р±Р»РёС†Р° РґР»СЏ РІРѕРґСЏРЅС‹С… Р·РЅР°РєРѕРІ (watermarks)
CREATE TABLE IF NOT EXISTS meta.watermarks
(
    source       LowCardinality(String),   -- 'qtickets','vk_ads'
    stream       LowCardinality(String),   -- 'orders','ads_daily'
    wm_type      LowCardinality(String),   -- 'updated_at','id','date'
    wm_value_s   String,                   -- С…СЂР°РЅРµРЅРёРµ РІ СЃС‚СЂРѕРєРµ (ISO/С‡РёСЃР»Рѕ)
    updated_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (source, stream);

-- 2. РЎС‚РµР№РґР¶РёРЅРі РґР»СЏ СЃРѕР±С‹С‚РёР№ РїСЂРѕРґР°Р¶ (CDC СЃР»РѕР№)
CREATE TABLE IF NOT EXISTS zakaz.stg_sales_events
(
    event_date     Date,
    event_id       String,
    city           String,
    order_id       String,
    tickets_sold   Int32,
    net_revenue    Float64,
    currency       LowCardinality(String),

    _src           LowCardinality(String) DEFAULT 'qtickets',
    _op            LowCardinality(String) DEFAULT 'UPSERT',  -- 'UPSERT'|'DELETE'
    _ver           UInt64,                                   -- РІРµСЂСЃРёРѕРЅРёСЂРѕРІР°РЅРёРµ (ts ms)
    _loaded_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, city, event_id, order_id);

-- 3. РЎС‚РµР№РґР¶РёРЅРі РґР»СЏ VK Ads (CDC СЃР»РѕР№)
CREATE TABLE IF NOT EXISTS zakaz.stg_vk_ads_daily
(
    stat_date      Date,
    city           String,
    campaign_id    String,
    ad_id          String,
    impressions    UInt64,
    clicks         UInt64,
    spend          Float64,

    _src        LowCardinality(String) DEFAULT 'vk_ads',
    _op         LowCardinality(String) DEFAULT 'UPSERT',
    _ver        UInt64,
    _loaded_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(stat_date)
ORDER BY (stat_date, city, campaign_id, ad_id);

-- 4. TTL РґР»СЏ СЃС‚РµР№РґР¶РёРЅРіРѕРІ (С…СЂР°РЅРёС‚СЊ 30 РґРЅРµР№)
ALTER TABLE zakaz.stg_sales_events
MODIFY TTL _loaded_at + INTERVAL 30 DAY DELETE;

ALTER TABLE zakaz.stg_vk_ads_daily
MODIFY TTL _loaded_at + INTERVAL 30 DAY DELETE;

-- 5. РўР°Р±Р»РёС†Р° SLI РґР»СЏ РјРѕРЅРёС‚РѕСЂРёРЅРіР° СЃРІРµР¶РµСЃС‚Рё РґР°РЅРЅС‹С…
CREATE TABLE IF NOT EXISTS meta.sli_daily
(
    d                     Date,
    table_name            LowCardinality(String),
    metric_name           LowCardinality(String),
    metric_value          Float64,
    updated_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (d, table_name, metric_name);

-- 6. РџСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ РґР»СЏ РїРѕСЃР»РµРґРЅРёС… SLI
CREATE OR REPLACE VIEW meta.v_sli_latest AS
SELECT
    d,
    table_name,
    metric_name,
    metric_value,
    updated_at
FROM meta.sli_daily
WHERE d >= today() - 3
ORDER BY d DESC, table_name, metric_name;

-- Р’С‹РґР°С‡Р° РїСЂР°РІ РґР»СЏ РЅРѕРІС‹С… РѕР±СЉРµРєС‚РѕРІ

-- ========================================
-- EPIC-CH-05: BI-РЎР›РћР™ Р”Р›РЇ DATALENS
-- ========================================

-- РЎРѕР·РґР°РЅРёРµ Р‘Р” bi (РµСЃР»Рё РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚)
CREATE DATABASE IF NOT EXISTS bi;

-- 1) РџСЂРѕРґР°Р¶Рё (РґРµС€С‘РІС‹Р№ JOIN СЃ Р°Р»РёР°СЃР°РјРё РіРѕСЂРѕРґРѕРІ)
CREATE OR REPLACE VIEW bi.v_sales_daily AS
SELECT
  s.event_date                      AS d,
  lowerUTF8(trim(BOTH ' ' FROM coalesce(a.city, s.city))) AS city,
  s.event_id                        AS event_id,
  sum(s.tickets_sold)               AS tickets_sold,
  toDecimal64(sum(s.net_revenue) / 100, 2) AS revenue,
  anyLast(s.currency)               AS currency,
  max(s._loaded_at)                 AS _loaded_at
FROM zakaz.dm_sales_daily s
LEFT JOIN zakaz.dim_city_alias a ON lowerUTF8(s.city) = lowerUTF8(a.alias)
GROUP BY d, city, s.event_id;

-- 2) РњР°СЂРєРµС‚РёРЅРі (VK Ads)
CREATE OR REPLACE VIEW bi.v_vk_ads_daily AS
SELECT
  v.stat_date                       AS d,
  lowerUTF8(v.city)                 AS city,
  sum(v.impressions)                AS impressions,
  sum(v.clicks)                     AS clicks,
  toDecimal64(sum(v.spend) / 100, 2) AS spend,
  max(v._loaded_at)                 AS _loaded_at
FROM zakaz.dm_vk_ads_daily v
GROUP BY d, city;

-- 3) ROI (sales вџ· ads)
CREATE OR REPLACE VIEW bi.v_marketing_roi_daily AS
WITH j AS (
  SELECT
        coalesce(s.d, a.d)              AS d,
    coalesce(s.city, a.city)        AS city,
    s.revenue,
    s.tickets_sold,
    a.impressions,
    a.clicks,
    a.spend,
    max(
      ifNull(
        toUnixTimestamp(s._loaded_at),
        toUnixTimestamp(a._loaded_at)
      )
    ) AS _ts
  FROM bi.v_sales_daily s
  FULL OUTER JOIN bi.v_vk_ads_daily a USING (d, city)
  GROUP BY d, city, s.revenue, s.tickets_sold, a.impressions, a.clicks, a.spend
)
SELECT
  d, city,
  revenue, tickets_sold, impressions, clicks, spend,
  ifNull(revenue / nullIf(spend, 0), 0)      AS roas,
  spend / nullIf(clicks, 0)                  AS cpc,
  spend / nullIf(tickets_sold, 0)            AS cpt,
  toDateTime(_ts)                            AS _loaded_at
FROM j;

-- 4) Ops/Freshness
CREATE OR REPLACE VIEW bi.v_ops_freshness AS
SELECT
  today() AS d,
  'sales' AS source,
  maxIf(_loaded_at, table='dm_sales_daily') AS loaded_at_sales,
  maxIf(_loaded_at, table='dm_vk_ads_daily') AS loaded_at_vk,
  dateDiff('hour', maxIf(_loaded_at, table='dm_sales_daily'), now()) AS freshness_hours_sales,
  dateDiff('hour', maxIf(_loaded_at, table='dm_vk_ads_daily'), now()) AS freshness_hours_vk
FROM (
  SELECT today() AS d, 'dm_sales_daily' AS table, max(_loaded_at) AS _loaded_at FROM zakaz.dm_sales_daily
  UNION ALL
  SELECT today() AS d, 'dm_vk_ads_daily', max(_loaded_at) FROM zakaz.dm_vk_ads_daily
)
GROUP BY d
SETTINGS allow_experimental_object_type = 1;

-- Р’С‹РґР°С‡Р° РїСЂР°РІ РґР»СЏ BI-СЃР»РѕСЏ

-- ========================================
-- EPIC-CH-07: Р‘Р­РљРђРџР« Р Р’РћРЎРЎРўРђРќРћР’Р›Р•РќРР•
-- ========================================

-- РўР°Р±Р»РёС†Р° РґР»СЏ Р»РѕРіРёСЂРѕРІР°РЅРёСЏ Р±СЌРєР°РїРѕРІ
CREATE TABLE IF NOT EXISTS meta.backup_runs
(
    ts DateTime DEFAULT now(),
    backup_name String,
    mode Enum8('full' = 1, 'incr' = 2) DEFAULT 'full',
    target String,          -- s3://bucket/prefix ... РёР»Рё /local/path
    status Enum8('ok' = 1, 'fail' = 2, 'running' = 3) DEFAULT 'running',
    bytes UInt64 DEFAULT 0,
    duration_ms UInt64 DEFAULT 0,
    details String DEFAULT '',
    error_msg String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, backup_name, mode);

-- Р’С‹РґР°С‡Р° РїСЂР°РІ РґР»СЏ С‚Р°Р±Р»РёС†С‹ Р±СЌРєР°РїРѕРІ










