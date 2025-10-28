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

-- Old fact_qtickets_inventory removed - using fact_qtickets_inventory_latest instead

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
    max(start_date) AS latest_date,
    dateDiff('day', max(start_date), today()) AS days_behind,
    count() AS total_rows
FROM zakaz.dim_events

UNION ALL

SELECT
    'qtickets_sheets' AS source,
    'inventory' AS table_name,
    max(snapshot_ts) AS latest_date,
    dateDiff('day', max(snapshot_ts), today()) AS days_behind,
    count() AS total_rows
FROM zakaz.fact_qtickets_inventory_latest;

-- ========================================
-- ВЫДАЧА ПРАВ
-- ========================================

-- Права для ETL пользователя
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_raw TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_inventory TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dim_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_inventory TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.meta_job_runs TO etl_writer;

-- Права для DataLens пользователя
GRANT SELECT ON zakaz.v_qtickets_sales_latest TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_sales_14d TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_inventory TO datalens_reader;
GRANT SELECT ON zakaz.dim_events TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_sales TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_inventory TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_freshness TO datalens_reader;
GRANT SELECT ON zakaz.meta_job_runs TO datalens_reader;

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