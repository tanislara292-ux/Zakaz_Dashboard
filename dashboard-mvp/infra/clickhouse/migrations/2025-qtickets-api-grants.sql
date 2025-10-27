-- Optional grants for QTickets API deployment.
-- Apply manually depending on the ClickHouse user configuration on the target host.

-- Read access for BI users (datalens_reader is managed via users.xml in production).
GRANT SELECT ON zakaz.v_qtickets_sales_dashboard TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_sales_daily TO datalens_reader;
GRANT SELECT ON zakaz.dim_events TO datalens_reader;
GRANT SELECT ON zakaz.fact_qtickets_inventory_latest TO datalens_reader;

-- Write access for the ETL user that runs the loader container.
GRANT INSERT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer;
GRANT INSERT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer;
GRANT INSERT ON zakaz.dim_events TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_sales_daily TO etl_writer;
GRANT INSERT ON zakaz.fact_qtickets_inventory_latest TO etl_writer;
GRANT INSERT ON zakaz.meta_job_runs TO etl_writer;
