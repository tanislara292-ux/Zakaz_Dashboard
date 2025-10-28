/*
  Zakaz Dashboard ClickHouse schema bootstrap (DDL only).
  Derived from bootstrap_all.sql without GRANT statements.
  Run via: docker exec -i ch-zakaz clickhouse-client --user="${CLICKHOUSE_ADMIN_USER:-admin}" --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/bootstrap_schema.sql
*/

-- ## Step 1: Base schemas (init.sql)
-- Source: init.sql

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
    _ver            UInt64,
    _loaded_at      DateTime DEFAULT now()
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
    greatestOrNull(toUnixTimestamp(max(s._loaded_at)), toUnixTimestamp(max(a._loaded_at))) AS _ts
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

-- ## Step 2: QTickets sheets (init_qtickets_sheets.sql)
-- Source: init_qtickets_sheets.sql

-- DDL для QTickets Google Sheets интеграции
-- Создание таблиц для хранения данных из Google Sheets

-- ========================================
-- СТЕЙДИНГ ТАБЛИЦЫ
-- ========================================

-- Сырые данные из Google Sheets
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sheets_raw
(
    source           String,                    -- Источник данных (qtickets_sheets)
    sheet_id         String,                    -- ID таблицы Google Sheets
    tab              String,                    -- Имя листа
    payload_json     String,                    -- Сырые данные в JSON
    _ver             UInt64,                    -- Версия записи
    _ingest_ts       DateTime,                  -- Время загрузки
    hash_low_card    LowCardinality(String)      -- Хэш для дедупликации
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(_ingest_ts)
ORDER BY (source, sheet_id, tab, hash_low_card);

-- Стейджинг для мероприятий
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sheets_events
(
    event_id         String,                    -- ID мероприятия
    event_name       String,                    -- Название мероприятия
    event_date       Date,                      -- Дата мероприятия
    city             String,                    -- Город
    tickets_total    UInt32 DEFAULT 0,          -- Общее количество билетов
    tickets_left     UInt32 DEFAULT 0,          -- Доступно билетов
    _ver             UInt64,                    -- Версия записи
    hash_low_card    LowCardinality(String)      -- Хэш для дедупликации
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_id, city);

-- Стейджинг для инвентаря
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sheets_inventory
(
    event_id         String,                    -- ID мероприятия
    city             String,                    -- Город
    tickets_total    UInt32 DEFAULT 0,          -- Общее количество билетов
    tickets_left     UInt32 DEFAULT 0,          -- Доступно билетов
    _ver             UInt64,                    -- Версия записи
    hash_low_card    LowCardinality(String)      -- Хэш для дедупликации
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(today())
ORDER BY (event_id, city);

-- Стейджинг для продаж
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sheets_sales
(
    date             Date,                      -- Дата продажи
    event_id         String,                    -- ID мероприятия
    event_name       String,                    -- Название мероприятия
    city             String,                    -- Город
    tickets_sold     UInt32 DEFAULT 0,          -- Продано билетов
    revenue          Decimal(12,2) DEFAULT 0,   -- Выручка
    refunds          Decimal(12,2) DEFAULT 0,   -- Возвраты
    currency         FixedString(3) DEFAULT 'RUB', -- Валюта
    _ver             UInt64,                    -- Версия записи
    hash_low_card    LowCardinality(String)      -- Хэш для дедупликации
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(date)
ORDER BY (date, event_id, city);

-- ========================================
-- ФАКТ ТАБЛИЦЫ
-- ========================================

-- Справочник мероприятий (обновляем существующий)
CREATE TABLE IF NOT EXISTS zakaz.dim_events
(
    event_id         String,                    -- ID мероприятия
    event_name       String,                    -- Название мероприятия
    event_date       Date,                      -- Дата мероприятия
    city             String,                    -- Город
    tickets_total    UInt32 DEFAULT 0,          -- Общее количество билетов
    tickets_left     UInt32 DEFAULT 0,          -- Доступно билетов
    _ver             UInt64                     -- Версия записи
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_id, city);

-- Факт таблица инвентаря
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_inventory
(
    event_id         String,                    -- ID мероприятия
    city             String,                    -- Город
    tickets_total    UInt32 DEFAULT 0,          -- Общее количество билетов
    tickets_left     UInt32 DEFAULT 0,          -- Доступно билетов
    _ver             UInt64                     -- Версия записи
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(today())
ORDER BY (event_id, city);

-- Факт таблица продаж
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_sales
(
    date             Date,                      -- Дата продажи
    event_id         String,                    -- ID мероприятия
    event_name       String,                    -- Название мероприятия
    city             String,                    -- Город
    tickets_sold     UInt32 DEFAULT 0,          -- Продано билетов
    revenue          Decimal(12,2) DEFAULT 0,   -- Выручка
    refunds          Decimal(12,2) DEFAULT 0,   -- Возвраты
    currency         FixedString(3) DEFAULT 'RUB', -- Валюта
    _ver             UInt64                     -- Версия записи
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(date)
ORDER BY (date, event_id, city);

-- ========================================
-- ПРЕДСТАВЛЕНИЯ ДЛЯ BI
-- ========================================

-- Актуальные продажи (без дублей)
CREATE OR REPLACE VIEW zakaz.v_qtickets_sales_latest AS
SELECT 
    date,
    event_id,
    event_name,
    city,
    tickets_sold,
    revenue,
    refunds,
    currency
FROM zakaz.fact_qtickets_sales FINAL;

-- Продажи за последние 14 дней
CREATE OR REPLACE VIEW zakaz.v_qtickets_sales_14d AS
SELECT
    date,
    city,
    event_id,
    event_name,
    sum(tickets_sold) AS tickets_sold,
    sum(revenue) AS revenue,
    sum(refunds) AS refunds,
    any(currency) AS currency
FROM zakaz.fact_qtickets_sales FINAL
WHERE date >= today() - 14
GROUP BY date, city, event_id, event_name
ORDER BY date DESC, city, event_id;

-- Инвентарь по мероприятиям
CREATE OR REPLACE VIEW zakaz.v_qtickets_inventory AS
SELECT
    event_id,
    city,
    tickets_total,
    tickets_left,
    tickets_total - tickets_left AS tickets_sold
FROM zakaz.fact_qtickets_inventory FINAL
ORDER BY city, event_id;

-- ========================================
-- МЕТАДАННЫЕ И МОНИТОРИНГ
-- ========================================

-- Таблица для метаданных запусков (если не существует)
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

-- Представление для проверки свежести данных
CREATE OR REPLACE VIEW zakaz.v_qtickets_freshness AS
SELECT
    'qtickets_sheets' AS source,
    'sales' AS table_name,
    max(date) AS latest_date,
    dateDiff('day', max(date), today()) AS days_behind,
    count() AS total_rows
FROM zakaz.fact_qtickets_sales

UNION ALL

SELECT
    'qtickets_sheets' AS source,
    'events' AS table_name,
    max(event_date) AS latest_date,
    dateDiff('day', max(event_date), today()) AS days_behind,
    count() AS total_rows
FROM zakaz.dim_events

UNION ALL

SELECT
    'qtickets_sheets' AS source,
    'inventory' AS table_name,
    today() AS latest_date,
    0 AS days_behind,
    count() AS total_rows
FROM zakaz.fact_qtickets_inventory;

-- ========================================
-- ВЫДАЧА ПРАВ
-- ========================================

-- Права для ETL пользователя

-- Права для DataLens пользователя

-- ========================================
-- TTL ДЛЯ СТЕЙДИНГ ТАБЛИЦ
-- ========================================

-- Хранение сырых данных 30 дней
ALTER TABLE zakaz.stg_qtickets_sheets_raw 
MODIFY TTL _ingest_ts + INTERVAL 30 DAY DELETE;

-- Хранение стейджинг данных 7 дней
ALTER TABLE zakaz.stg_qtickets_sheets_events 
MODIFY TTL _ver + toIntervalDay(7) DELETE;

ALTER TABLE zakaz.stg_qtickets_sheets_inventory 
MODIFY TTL _ver + toIntervalDay(7) DELETE;

ALTER TABLE zakaz.stg_qtickets_sheets_sales 
MODIFY TTL _ver + toIntervalDay(7) DELETE;

-- ## Step 3: Legacy integrations (init_integrations.sql)
-- Source: init_integrations.sql

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
ORDER BY (event_date, lowerUTF8(city), event_id, event_name);
ALTER TABLE zakaz.stg_qtickets_sales_raw ADD COLUMN IF NOT EXISTS event_id String AFTER event_date;

CREATE TABLE IF NOT EXISTS zakaz.dim_events
(
  event_id String,
  event_name String,
  event_date Date,
  city String,
  tickets_total Int32,
  tickets_left Int32,
  _ver DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_ver)
ORDER BY (event_date, event_id);

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
GROUP BY event_date, city, event_id, event_name;

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
  job String,
  started_at DateTime,
  finished_at DateTime,
  rows_processed UInt64,
  status LowCardinality(String),  -- success, error, running
  message String,
  metrics String
)
ENGINE = ReplacingMergeTree(started_at)
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

-- ## Step 4: QTickets final migration (2025-qtickets-api-final.sql)
-- Source: migrations/2025-qtickets-api-final.sql

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


-- ## Step 5 (optional): Grants for service accounts (2025-qtickets-api-grants.sql)
-- Source: migrations/2025-qtickets-api-grants.sql
-- Optional block: failing statements do not block the bootstrap.

-- Optional grants for QTickets API deployment.
-- Apply manually depending on the ClickHouse user configuration on the target host.

-- Ensure datalens_reader exists so that GRANT statements succeed (no-op if defined in users.d).

-- Read access for BI users (datalens_reader is managed via users.xml in production).

-- Write access for the ETL user that runs the loader container.
















