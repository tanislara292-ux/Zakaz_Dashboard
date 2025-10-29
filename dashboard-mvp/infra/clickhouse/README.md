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
- `bootstrap_grants.sql` — optional grants for BI and service accounts.
- `../scripts/bootstrap_clickhouse.sh` — automation for the manual flow.

## Manual step-by-step bootstrap

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

# 5. Apply schema (no GRANT statements here)
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  < bootstrap_schema.sql

# 6. Inspect tables (expect stg_qtickets_api_orders_raw, stg_qtickets_api_inventory_raw,
#    fact_qtickets_sales_daily, fact_qtickets_inventory_latest, mv_qtickets_sales_latest,
#    meta_job_runs, v_qtickets_sales_dashboard, etc.)
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  -q "SHOW TABLES FROM zakaz;"

# 7. (Optional) Grant BI/service access
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  < bootstrap_grants.sql
```

If step 7 fails with `ACCESS_DENIED`, the executing account lacks grant
privileges. Run the file with a superuser or adjust `users.d` as needed; the
schema remains fully provisioned.

## Automated bootstrap helper

Instead of running steps 2–6 manually you can execute:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
../scripts/bootstrap_clickhouse.sh
```

The script:

- Verifies that `.env` exists and loads credentials.
- Creates `data/` and `logs/` (attempts to chown to UID 101).
- Starts the compose stack and waits until `ch-zakaz` reports `healthy`.
- Applies `bootstrap_schema.sql` and prints the resulting tables.

It also prints the exact `docker exec` command to apply `bootstrap_grants.sql`
afterwards.

## Reset / tear-down

- `docker compose down` — stop the service, keep data.
- `docker compose down -v` — stop and remove data directories (only for
  non-production environments; rerun the bootstrap afterwards).

Whenever you recreate the volumes, repeat the permission step so ClickHouse can
access the directories.
## Yandex DataLens Integration

After running `docker compose up -d`, two users are automatically created:

### Users and Credentials

| User | Password | Access | Network |
|------|----------|--------|---------|
| **admin** | `admin_pass` | Full access | `::/0` (all) |
| **datalens_reader** | `ChangeMe123!` | Read-only on `zakaz.*` | `::/0` (all) |

⚠️ **IMPORTANT**: The `ChangeMe123!` password is a placeholder. For production deployments, change it using:
```bash
# Method 1: Change password directly
ALTER USER datalens_reader IDENTIFIED WITH plaintext_password BY 'your_secure_password';

# Method 2: Edit users.d/datalens-user.xml and restart
# Update the password field, then:
docker compose restart ch-zakaz
```

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
