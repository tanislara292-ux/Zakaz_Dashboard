-- DDL для почтового инжестора (Gmail → ClickHouse)
-- Этот файл создает таблицы и витрины для обработки данных из почтовых отчетов

CREATE DATABASE IF NOT EXISTS zakaz;

-- Сырая таблица из почты (последняя версия строки выбирается по msg_received_at)
CREATE TABLE IF NOT EXISTS zakaz.stg_mail_sales_raw
(
  msg_id           String,
  msg_received_at  DateTime,
  source           LowCardinality(String),  -- 'gmail'
  event_date       Date,
  event_id         String,                  -- как в письме (или нормализованный id)
  event_name       String,
  city             String,
  tickets_sold     Int32,
  revenue          Float64,
  refunds          Float64,
  currency         LowCardinality(String),
  row_hash         String,                  -- для трассировки/диагностики
  _ingested_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(msg_received_at)
ORDER BY (event_date, lowerUTF8(city), event_name);

-- Витрина "последнее значение по ключу" (без дублей из повторных писем)
CREATE OR REPLACE VIEW zakaz.v_sales_latest AS
SELECT
  event_date,
  argMax(event_id,        msg_received_at) AS event_id,
  argMax(event_name,      msg_received_at) AS event_name,
  city,
  argMax(tickets_sold,    msg_received_at) AS tickets_sold,
  argMax(revenue,         msg_received_at) AS revenue,
  argMax(refunds,         msg_received_at) AS refunds,
  argMax(currency,        msg_received_at) AS currency
FROM zakaz.stg_mail_sales_raw
GROUP BY event_date, event_name, city;

-- Витрина для быстрых графиков за 14 дней
CREATE OR REPLACE VIEW zakaz.v_sales_14d AS
SELECT
  event_date AS d,
  sum(tickets_sold)                               AS tickets,
  sum(revenue - refunds)                          AS net_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 14
GROUP BY d
ORDER BY d;

-- Обновленная витрина для DataLens с совместимостью с существующей структурой
CREATE OR REPLACE VIEW zakaz.v_sales_combined AS
SELECT
  event_date,
  event_name,
  city,
  tickets_sold,
  revenue,
  refunds,
  revenue - refunds AS net_revenue,
  currency,
  _ingested_at
FROM zakaz.v_sales_latest
UNION ALL
SELECT
  event_date,
  event_name,
  city,
  tickets_sold,
  revenue,
  refunds_amount AS refunds,
  revenue - refunds_amount AS net_revenue,
  currency,
  now() AS _ingested_at
FROM zakaz.stg_qtickets_sales FINAL;

-- Выдача прав пользователям
GRANT SELECT ON zakaz.stg_mail_sales_raw TO datalens_reader;
GRANT INSERT, SELECT ON zakaz.stg_mail_sales_raw TO etl_writer;
GRANT SELECT ON zakaz.v_sales_latest TO datalens_reader;
GRANT SELECT ON zakaz.v_sales_14d TO datalens_reader;
GRANT SELECT ON zakaz.v_sales_combined TO datalens_reader;