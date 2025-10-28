-- Создание БД zakaz (если не существует)
CREATE DATABASE IF NOT EXISTS zakaz;

-- Стейджинг — заказы QTickets
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
ALTER TABLE zakaz.stg_qtickets_sales ADD COLUMN IF NOT EXISTS event_id String AFTER event_date;

-- Стейджинг — VK Ads (суточная статистика)
CREATE TABLE IF NOT EXISTS zakaz.stg_vk_ads_daily
(
    stat_date   Date,
    campaign_id UInt64,
    ad_id       UInt64,
    impressions UInt64,
    clicks      UInt64,
    spent       Decimal(12,2),

    utm_source  String,
    utm_medium  String,
    utm_campaign String,
    utm_content String,
    utm_term    String,

    dedup_key   String,               -- "<stat_date>|<campaign_id>|<ad_id>"
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (stat_date, campaign_id, ad_id);

-- Каркас ядра — фактовая таблица продаж (пока пустая логика, только DDL)
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
ALTER TABLE zakaz.core_sales_fct ADD COLUMN IF NOT EXISTS event_id String AFTER event_date;

-- Представления для DataLens (BI-слой без дублей)
-- 2.1. Представление по продажам (без дублей)
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

-- 2.2. Укрупнение «за 14 дней» (опционально — для быстрых графиков)
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

-- Выдача прав пользователям
GRANT SELECT ON zakaz.* TO datalens_reader;
GRANT INSERT, SELECT ON zakaz.* TO etl_writer;

-- Дополнительные права для DataLens (если нужно ограничить доступ только к BI-слою)
-- REVOKE SELECT ON zakaz.* FROM datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_latest TO datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_14d TO datalens_reader;
-- GRANT SELECT ON zakaz.stg_qtickets_sales TO datalens_reader;

-- ========================================
-- EPIC-CH-03: МАТЕРИАЛИЗОВАННЫЕ ВИТРИНЫ
-- ========================================

-- 1.1 Материализованная витрина продаж
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
ALTER TABLE zakaz.dm_sales_daily ADD COLUMN IF NOT EXISTS event_id LowCardinality(String) AFTER sale_date;
ALTER TABLE zakaz.dm_sales_daily ADD COLUMN IF NOT EXISTS currency LowCardinality(String) DEFAULT 'RUB' AFTER net_revenue;
ALTER TABLE zakaz.dm_sales_daily ADD COLUMN IF NOT EXISTS _loaded_at DateTime DEFAULT now() AFTER currency;

-- 1.2 Прослойка для BI (плоское представление)
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

-- 2.1 Стейдж VK Ads (сырые суточные агрегации)
-- Обновляем существующую таблицу с дополнительными полями
DROP TABLE IF EXISTS zakaz.stg_vk_ads_daily;
CREATE TABLE IF NOT EXISTS zakaz.stg_vk_ads_daily
(
    stat_date       Date,
    account_id      UInt64,
    campaign_id     UInt64,
    ad_id           UInt64,
    utm_source      LowCardinality(String),
    utm_medium      LowCardinality(String),
    utm_campaign    String,
    utm_content     String,
    utm_term        String,
    impressions     UInt64,
    clicks          UInt64,
    spend           UInt64,  -- в копейках для целостности
    currency        LowCardinality(String),
    city_raw        String,  -- извлечённый из UTM/названия кампании
    _dedup_key      UInt64,  -- sipHash64(...) уникальность строки
    _ver            UInt64
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(stat_date)
ORDER BY (stat_date, account_id, campaign_id, ad_id, _dedup_key);

-- 2.2 Справочник алиасов городов (канонизация)
CREATE TABLE IF NOT EXISTS zakaz.dim_city_alias
(
    alias  LowCardinality(String),
    city   LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY (alias);

-- 2.3 Ежедневная витрина VK Ads
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
ALTER TABLE zakaz.dm_vk_ads_daily ADD COLUMN IF NOT EXISTS _loaded_at DateTime DEFAULT now() AFTER spend;

-- 2.4 Представления для BI
CREATE OR REPLACE VIEW zakaz.v_vk_ads_daily AS
SELECT stat_date, city, impressions, clicks, spend
FROM zakaz.dm_vk_ads_daily;

-- 2.5 Сводная ROI (только представление, без хранения)
CREATE OR REPLACE VIEW zakaz.v_marketing_roi_daily AS
SELECT
    s.event_date                   AS d,
    s.city                         AS city,
    sum(s.net_revenue)             AS net_revenue,
    sum(s.tickets_sold)            AS tickets_sold,
    sum(v.spend)                   AS spend,
    sum(v.clicks)                  AS clicks,
    sum(v.impressions)             AS impressions,
    -- простейшие показатели
    if(sum(v.spend)=0, 0, sum(s.net_revenue) / sum(v.spend)) AS roas,
    if(sum(v.clicks)=0, 0, sum(v.spend) / sum(v.clicks))     AS cpc,
    if(sum(s.tickets_sold)=0, 0, sum(v.spend)/sum(s.tickets_sold)) AS cpt
FROM zakaz.dm_sales_daily AS s
LEFT JOIN zakaz.dm_vk_ads_daily AS v
    ON v.stat_date = s.event_date
   AND v.city = s.city
GROUP BY d, city;

-- Выдача прав для новых объектов
GRANT SELECT ON zakaz.dm_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_dm_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_vk_ads_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_marketing_roi_daily TO datalens_reader;
GRANT SELECT ON zakaz.dm_vk_ads_daily TO datalens_reader;
GRANT SELECT ON zakaz.dim_city_alias TO datalens_reader;

-- ========================================
-- EPIC-CH-04: ETL ОРКЕСТРАЦИЯ И МОНИТОРИНГ
-- ========================================

-- Создание схемы meta, если не существует
CREATE DATABASE IF NOT EXISTS meta;

-- 1.1 реестр прогонов ETL
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

-- 1.2 реестр алертов
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

-- 1.3 быстрые проверки качества последнего дня
CREATE OR REPLACE VIEW meta.v_quality_last_day AS
SELECT
    today() - 1 AS d,
    (SELECT count() FROM zakaz.dm_sales_daily WHERE event_date = today() - 1)          AS sales_rows,
    (SELECT sum(net_revenue) FROM zakaz.dm_sales_daily WHERE event_date = today() - 1) AS sales_revenue,
    (SELECT count() FROM zakaz.dm_vk_ads_daily WHERE stat_date = today() - 1)          AS vk_rows,
    (SELECT sum(spend) FROM zakaz.dm_vk_ads_daily WHERE stat_date = today() - 1)       AS vk_spend;

-- Выдача прав для новых объектов
GRANT SELECT ON meta.* TO etl_writer;
GRANT SELECT ON meta.* TO datalens_reader;

-- ========================================
-- EPIC-CH-06: ИНКРЕМЕНТАЛЬНЫЕ CDC-ЗАГРУЗКИ И NRT
-- ========================================

-- 1. Таблица для водяных знаков (watermarks)
CREATE TABLE IF NOT EXISTS meta.watermarks
(
    source       LowCardinality(String),   -- 'qtickets','vk_ads'
    stream       LowCardinality(String),   -- 'orders','ads_daily'
    wm_type      LowCardinality(String),   -- 'updated_at','id','date'
    wm_value_s   String,                   -- хранение в строке (ISO/число)
    updated_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (source, stream);

-- 2. Стейджинг для событий продаж (CDC слой)
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
    _ver           UInt64,                                   -- версионирование (ts ms)
    _loaded_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, city, event_id, order_id);

-- 3. Стейджинг для VK Ads (CDC слой)
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

-- 4. TTL для стейджингов (хранить 30 дней)
ALTER TABLE zakaz.stg_sales_events
MODIFY TTL _loaded_at + INTERVAL 30 DAY DELETE;

ALTER TABLE zakaz.stg_vk_ads_daily
MODIFY TTL _loaded_at + INTERVAL 30 DAY DELETE;

-- 5. Таблица SLI для мониторинга свежести данных
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

-- 6. Представление для последних SLI
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

-- Выдача прав для новых объектов
GRANT SELECT ON meta.watermarks TO etl_writer;
GRANT SELECT ON meta.watermarks TO datalens_reader;
GRANT INSERT, SELECT ON zakaz.stg_sales_events TO etl_writer;
GRANT SELECT ON zakaz.stg_sales_events TO datalens_reader;
GRANT INSERT, SELECT ON zakaz.stg_vk_ads_daily TO etl_writer;
GRANT SELECT ON zakaz.stg_vk_ads_daily TO datalens_reader;
GRANT SELECT ON meta.sli_daily TO etl_writer;
GRANT SELECT ON meta.sli_daily TO datalens_reader;
GRANT SELECT ON meta.v_sli_latest TO etl_writer;
GRANT SELECT ON meta.v_sli_latest TO datalens_reader;

-- ========================================
-- EPIC-CH-05: BI-СЛОЙ ДЛЯ DATALENS
-- ========================================

-- Создание БД bi (если не существует)
CREATE DATABASE IF NOT EXISTS bi;

-- 1) Продажи (дешёвый JOIN с алиасами городов)
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

-- 2) Маркетинг (VK Ads)
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

-- 3) ROI (sales ⟷ ads)
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

-- Выдача прав для BI-слоя
GRANT SELECT ON bi.* TO datalens_reader;

-- ========================================
-- EPIC-CH-07: БЭКАПЫ И ВОССТАНОВЛЕНИЕ
-- ========================================

-- Таблица для логирования бэкапов
CREATE TABLE IF NOT EXISTS meta.backup_runs
(
    ts DateTime DEFAULT now(),
    backup_name String,
    mode Enum8('full' = 1, 'incr' = 2) DEFAULT 'full',
    target String,          -- s3://bucket/prefix ... или /local/path
    status Enum8('ok' = 1, 'fail' = 2, 'running' = 3) DEFAULT 'running',
    bytes UInt64 DEFAULT 0,
    duration_ms UInt64 DEFAULT 0,
    details String DEFAULT '',
    error_msg String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, backup_name, mode);

-- Выдача прав для таблицы бэкапов
GRANT INSERT, SELECT ON meta.backup_runs TO backup_user;
GRANT SELECT ON meta.backup_runs TO etl_writer;
GRANT SELECT ON meta.backup_runs TO datalens_reader;
GRANT SELECT ON meta.backup_runs TO admin_min;







