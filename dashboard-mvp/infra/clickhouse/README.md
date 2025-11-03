# ClickHouse Bootstrap

ClickHouse must be deployable on a clean Ubuntu host that only has Docker and
docker compose installed. Follow the steps below without editing SQL or Python
sources.

## Required files

- `docker-compose.yml` and `.env.example` — single ClickHouse service, no extra
  proxies.
- `config.d/`, `users.d/` — bundled server configuration.
- `bootstrap_schema.sql` — creates every object required by the Zakaz dashboards
  and the QTickets integration (`meta_job_runs`, `stg_qtickets_api_*`, facts,
  views, materialized views, etc.).
- `bootstrap_roles_grants.sql` — canonical roles + service-account privileges
  (idempotent, safe to re-run).
- `../scripts/bootstrap_clickhouse.sh` — automation for the manual flow.
- `../scripts/bootstrap_datalens.sh` — quick verification of the BI reader.

## Complete Deployment Instructions (Copy-Paste Ready)

```bash
# 1. Clone and prepare
git clone <repository_url> Zakaz_Dashboard
cd Zakaz_Dashboard/dashboard-mvp/infra/clickhouse
cp .env.example .env

# 2. Bootstrap ClickHouse (schema + roles)
../../scripts/bootstrap_clickhouse.sh
# Expected output: "ClickHouse is healthy", list of tables, SHOW GRANTS dumps

# 3. Verify DataLens user access (optional but recommended)
../../scripts/bootstrap_datalens.sh

# 4. Test ETL integration (dry run)
cd ../..
./scripts/smoke_qtickets_dryrun.sh
# Expected output: "Dry-run completed successfully with no ClickHouse writes"
```

⚠️ **IMPORTANT:** Admin user is created exclusively via `users.d/00-admin.xml`, not through environment variables. Do NOT set CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB in docker-compose.yml as this causes ClickHouse to create conflicting default-user.xml file.

## Manual step-by-step bootstrap (for debugging)

```bash
# 1. Preparation
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
cp .env.example .env

# 2. Create data directories for ClickHouse volumes
mkdir -p data logs
sudo chown -R 101:101 data logs

# 3. Start ClickHouse
docker compose up -d

# 4. Verify connectivity
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  -q "SELECT 'clickhouse_ok';"

# 5. Apply schema (DDL only)
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  < bootstrap_schema.sql

# 6. Apply roles & grants
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  < bootstrap_roles_grants.sql

# 7. Inspect tables (expect stg_qtickets_api_orders_raw, stg_qtickets_api_inventory_raw,
#    fact_qtickets_sales_daily, fact_qtickets_inventory_latest, mv_qtickets_sales_latest,
#    meta_job_runs, v_qtickets_sales_dashboard, etc.)
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  -q "SHOW TABLES FROM zakaz;"
```

## Automated bootstrap helper

Instead of running steps 2–6 manually you can execute:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
../../scripts/bootstrap_clickhouse.sh
```

The script:

- Verifies that `.env` exists and loads credentials.
- Creates `data/` and `logs/` (attempts to chown to UID 101).
- Starts the compose stack and waits until `ch-zakaz` reports `healthy`.
- Applies `bootstrap_schema.sql` **and** `bootstrap_roles_grants.sql`.
- Lists the resulting tables and runs `SHOW GRANTS` for `admin` and
  `datalens_reader` so you can confirm RBAC is in place.

## Reset / tear-down

- `docker compose down` — stop the service, keep data.
- `docker compose down -v` — stop and remove data directories (only for
  non-production environments; rerun the bootstrap afterwards).

Whenever you recreate the volumes, repeat the permission step so ClickHouse can
access the directories.
## Yandex DataLens Integration

After running `docker compose up -d`, two users are automatically created:

### Users and Credentials

| User | Password | Access | Network | Purpose |
|------|----------|--------|---------|---------|
| **admin** | `admin_pass` | Full access + GRANT option | `::/0` (all) | System administration |
| **datalens_reader** | `ChangeMe123!` | Read-only on `zakaz.*` via role_bi_reader | `::/0` (all) | Yandex DataLens |
| **etl_writer** | `EtL2024!Strong#Pass` | INSERT/SELECT on staging tables | `127.0.0.1, ::1` | ETL processes |
| **backup_user** | `Backup2024!Strong#Pass` | Read access for backups | `127.0.0.1, ::1` | Backup operations |

⚠️ **IMPORTANT**: The `ChangeMe123!` password is a placeholder. For production deployments, change it using:
```bash
# Method 1: Change password directly
ALTER USER datalens_reader IDENTIFIED WITH plaintext_password BY 'your_secure_password';

# Method 2: Edit users.d/10-service-users.xml and restart
# Update the password field for datalens_reader, then:
docker compose restart ch-zakaz
```

### Default User Configuration

⚠️ **CRITICAL**: The default ClickHouse user (`default`) is **removed** via `users.d/00-admin.xml`. If you encounter a `default-user.xml` file in the container (`/etc/clickhouse-server/users.d/`), this indicates a configuration error - the container environment variables are creating a conflicting default user. Ensure that CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, and CLICKHOUSE_DB are NOT set as environment variables in docker-compose.yml.

### Testing DataLens Connection

Verify the datalens_reader can access ClickHouse:

```bash
# Test with curl (returns "1")
curl -u datalens_reader:ChangeMe123! http://localhost:8123/?query=SELECT%201

# Test with clickhouse-client (returns table count)
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password=ChangeMe123! \
  -q "SELECT count() FROM system.tables WHERE database='zakaz';"
```

The helper script `../../scripts/bootstrap_datalens.sh` runs the checks above
automatically and prints the relevant grants.

### DataLens Connection Parameters

For Yandex DataLens setup:

1. **Host**: Your ClickHouse server address
2. **Port**: `8123` (HTTP interface)
3. **Database**: `zakaz`
4. **Username**: `datalens_reader`
5. **Password**: `ChangeMe123!` (or your changed password)
6. **HTTPS**: Disabled by default (enable if using HTTPS/proxy)

If using HTTPS or reverse proxy, configure additional settings in DataLens and ensure the ClickHouse HTTP interface is properly secured.

## Schema validation

Before submitting SQL changes run the static checker to catch missing columns or
non-deterministic partition keys:

```bash
python scripts/validate_clickhouse_schema.py
```

Integrate the same command into CI (GitHub Actions, GitLab CI, etc.) so pull
requests fail fast when DDL/view dependencies drift.
