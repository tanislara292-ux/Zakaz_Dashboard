/*
  ClickHouse grants for Zakaz dashboard users.
  Run after bootstrap_schema.sql with admin user (has access_management=1).
  Users are created via XML configuration, grants applied via SQL.
*/

-- Grant SELECT permissions to datalens_reader on all zakaz tables and views
GRANT SELECT ON zakaz.* TO datalens_reader;

-- Grant INSERT and SELECT permissions to etl_writer for required tables
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
GRANT INSERT, SELECT ON zakaz.meta_job_runs TO etl_writer;

-- Grant backup permissions
GRANT SELECT ON zakaz.* TO backup_user;
GRANT INSERT, SELECT ON meta.backup_runs TO backup_user;