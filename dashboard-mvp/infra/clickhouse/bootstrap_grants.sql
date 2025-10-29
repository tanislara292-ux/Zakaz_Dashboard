/*
  Optional ClickHouse grants for Zakaz dashboard.
  Run manually after bootstrap_schema.sql if the executing user has grant privileges.
  Note: datalens_reader user is created via XML configuration in users.d/datalens-user.xml
*/

-- Grant permissions to datalens_reader (user created via XML)
GRANT SELECT ON zakaz.* TO datalens_reader;
GRANT INSERT, SELECT ON zakaz.* TO etl_writer;
GRANT SELECT ON zakaz.dm_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_dm_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_vk_ads_daily TO datalens_reader;
GRANT SELECT ON zakaz.v_marketing_roi_daily TO datalens_reader;
GRANT SELECT ON zakaz.dm_vk_ads_daily TO datalens_reader;
GRANT SELECT ON zakaz.dim_city_alias TO datalens_reader;
GRANT SELECT ON meta.* TO etl_writer;
GRANT SELECT ON meta.* TO datalens_reader;
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
GRANT SELECT ON bi.* TO datalens_reader;
GRANT INSERT, SELECT ON meta.backup_runs TO backup_user;
GRANT SELECT ON meta.backup_runs TO etl_writer;
GRANT SELECT ON meta.backup_runs TO datalens_reader;
GRANT SELECT ON meta.backup_runs TO admin_min;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_raw TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_inventory TO etl_writer;
GRANT INSERT, SELECT ON zakaz.stg_qtickets_sheets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.dim_events TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_inventory_latest TO etl_writer;
GRANT INSERT, SELECT ON zakaz.fact_qtickets_sales TO etl_writer;
GRANT INSERT, SELECT ON zakaz.meta_job_runs TO etl_writer;
GRANT SELECT ON zakaz.v_qtickets_sales_latest TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_sales_14d TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_inventory TO datalens_reader;
GRANT SELECT ON zakaz.dim_events TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_sales TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_inventory_latest TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_freshness TO datalens_reader;
GRANT SELECT ON zakaz.meta_job_runs TO datalens_reader;
GRANT SELECT ON zakaz.v_qtickets_sales_dashboard TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.dim_events TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_inventory_latest TO datalens_reader;
GRANT INSERT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer;
GRANT INSERT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer;
GRANT INSERT ON zakaz.dim_events TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_sales_daily TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_inventory_latest TO etl_writer;
GRANT INSERT ON zakaz.meta_job_runs TO etl_writer;
