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
## Schema validation

Before submitting SQL changes run the static checker to catch missing columns or
non-deterministic partition keys:

```bash
python scripts/validate_clickhouse_schema.py
```

Integrate the same command into CI (GitHub Actions, GitLab CI, etc.) so pull
requests fail fast when DDL/view dependencies drift.
