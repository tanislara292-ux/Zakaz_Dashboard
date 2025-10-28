# Canonical Schemas (from bootstrap_schema.sql)

## zakaz.dim_events
```sql
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
```

## zakaz.fact_qtickets_inventory (not used directly, replaced by _latest)

## zakaz.fact_qtickets_inventory_latest
```sql
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
```

## zakaz.stg_vk_ads_daily
```sql
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
ORDER BY (city, campaign_id, ad_id, stat_date)
SETTINGS index_granularity = 8192;
```

## zakaz.stg_qtickets_api_orders_raw
```sql
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
```

## zakaz.stg_qtickets_api_inventory_raw
```sql
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_api_inventory_raw
(
    snapshot_ts   DateTime,         -- Snapshot timestamp (MSK)
    event_id      String,           -- Event identifier
    event_name    String,           -- Event name
    city          LowCardinality(String), -- City (lowercase, normalized)
    tickets_total UInt32,           -- Total tickets
    tickets_left  UInt32,           -- Available tickets
    _ver          UInt64,           -- Version for ReplacingMergeTree
    _dedup_key    FixedString(32)  -- MD5 hash for deduplication
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()  -- No partitioning for small tables
ORDER BY (_dedup_key) -- Primary key for deduplication
SETTINGS index_granularity = 8192;
```

## zakaz.fact_qtickets_sales_daily
```sql
CREATE TABLE IF NOT EXISTS zakaz.fact_qtickets_sales_daily
(
    date          Date,             -- Sale date (MSK)
    city          LowCardinality(String), -- City (lowercase, normalized)
    event_id      String,           -- Event identifier
    event_name    String,           -- Event name
    tickets_sold  UInt32,           -- Total tickets sold that day
    revenue       Float64,          -- Total revenue (RUB)
    refunds       UInt32 DEFAULT 0, -- Number of refunded tickets
    currency      LowCardinality(String) DEFAULT 'RUB', -- Currency code

    _ver          UInt64,           -- Version for ReplacingMergeTree
    _loaded_at    DateTime DEFAULT now() -- Load timestamp
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY toYYYYMM(date)  -- Monthly partition for time series
ORDER BY (event_id, date, city)  -- Primary key for time series queries
SETTINGS index_granularity = 8192;
```
