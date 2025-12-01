/*
  ClickHouse roles and grants for Zakaz Dashboard.
  Run after bootstrap_schema.sql using an account with access_management=1 (admin/admin_pass).

  The script is idempotent and safe to re-run.
*/

-- ---------------------------------------------------------------------------
-- Role definitions
-- ---------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS role_bi_reader;
CREATE ROLE IF NOT EXISTS role_etl_writer;
CREATE ROLE IF NOT EXISTS role_backup_operator;

-- ---------------------------------------------------------------------------
-- Privileges for BI / DataLens consumers
-- ---------------------------------------------------------------------------
GRANT SELECT ON zakaz.* TO role_bi_reader;
GRANT SELECT ON meta.* TO role_bi_reader;
GRANT SELECT ON bi.* TO role_bi_reader;
GRANT SELECT ON system.query_log TO role_bi_reader;
GRANT SELECT ON system.part_log TO role_bi_reader;
GRANT SELECT ON system.tables TO role_bi_reader;
GRANT SELECT ON system.databases TO role_bi_reader;

-- ---------------------------------------------------------------------------
-- Privileges for ETL writer jobs
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT ON zakaz.* TO role_etl_writer;
GRANT SELECT ON meta.* TO role_etl_writer;

-- ---------------------------------------------------------------------------
-- Privileges for backup automation
-- ---------------------------------------------------------------------------
GRANT SELECT ON zakaz.* TO role_backup_operator;
GRANT SELECT, INSERT ON meta.backup_runs TO role_backup_operator;

-- ---------------------------------------------------------------------------
-- Assign roles to users
-- ---------------------------------------------------------------------------
-- NOTE: users defined in users.d XML cannot be updated via SQL (storage readonly).
-- If your service users live in XML (datalens_reader, etl_writer, backup_user),
-- assign the roles directly in users.d/*.xml. Grant roles here only for RBAC users.

-- Ensure the administrator inherits all roles for convenience.
GRANT role_bi_reader, role_etl_writer, role_backup_operator TO admin;
