/*
  ClickHouse grants для Zakaz dashboard.
  Запускается после bootstrap_schema.sql от имени пользователя admin/admin_pass.
  Пользователи создаются через XML, здесь только выдача прав.
*/

-- Read-only доступ для BI / DataLens
GRANT SELECT ON zakaz.* TO datalens_reader;
GRANT SELECT ON meta.* TO datalens_reader;
GRANT SELECT ON bi.* TO datalens_reader;

-- Права на системные журналы (используются в диагностике DataLens)
GRANT SELECT ON system.query_log TO datalens_reader;
GRANT SELECT ON system.part_log TO datalens_reader;

-- Права записи для загрузчика QTickets
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_raw TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_inventory TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_sales_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_vk_ads_daily TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dim_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dim_city_alias TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_inventory TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_sales_daily TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_inventory_latest TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dm_sales_daily TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dm_vk_ads_daily TO etl_writer;
GRANT INSERT ON zakaz.meta_job_runs TO etl_writer;

-- Аккаунт резервного копирования
GRANT SELECT ON zakaz.* TO backup_user;
GRANT INSERT, SELECT ON meta.backup_runs TO backup_user;
